from dataclasses import dataclass
import functools
import json
from pathlib import Path
import typing
from typing import IO, Any, Dict, List, NamedTuple, Optional, Sequence, Tuple, Type, Union, Callable, Literal, Iterable
import zipfile
import inspect

import numpy as np
import pandas as pd

from muutils.json_serialize.util import JSONitem, Hashableitem, MonoTuple, UniversalContainer, ErrorMode, isinstance_namedtuple, try_catch, _recursive_hashify, string_as_lines
from muutils.json_serialize.array import serialize_array, ArrayMode, arr_metadata
from muutils.json_serialize.json_serialize import JsonSerializer, json_serialize, SerializerHandler, DEFAULT_HANDLERS, ObjectPath
from muutils.tensor_utils import NDArray
from muutils.sysinfo import SysInfo
from muutils.zanj.externals import ExternalItemType, ExternalItem, EXTERNAL_ITEMS_EXTENSIONS, ZANJ_MAIN, ZANJ_META, EXTERNAL_ITEMS_EXTENSIONS_INV

ExternalsLoadingMode = Literal["lazy", "full"]


def load_ndarray(zanj: "LoadedZANJ", fp: IO[bytes]) -> NDArray:
	return np.load(fp)

def load_jsonl(zanj: "LoadedZANJ", fp: IO[bytes]) -> list[JSONitem]:
	return [
		json.loads(line) 
		for line in fp
	]

EXTERNAL_LOAD_FUNCS: dict[ExternalItemType, Callable[["ZANJ", IO[bytes]], Any]] = {
	"ndarray": load_ndarray,
	"jsonl": load_jsonl,
}


@dataclass
class LoaderHandler:
	"""handler for loading an object from a json file"""
	# (json_data, path) -> whether to use this handler
	check: Callable[[JSONitem, ObjectPath], bool]
	# function to load the object
	load: Callable[[JSONitem, ObjectPath], Any]
	# description of the handler
	desc: str = "(no description)"

@dataclass
class ZANJLoaderHandler:
	"""handler for loading an object from a ZANJ archive (takes ZANJ object as first arg)"""
	# (zanj_obi, json_data, path) -> whether to use this handler
	check: Callable[["ZANJ", JSONitem, ObjectPath], bool]
	# function to load the object (zanj_obj, json_data, path) -> loaded_obj
	load: Callable[["ZANJ", JSONitem, ObjectPath], Any]
	# TODO: add name/unique identifier, `desc` should be human-readable and more detailed
	# description of the handler
	desc: str = "(no description)"

	@classmethod
	def from_LoaderHandler(cls, lh: LoaderHandler):
		"""wrap a standard LoaderHandler to make it compatible with ZANJ"""
		return cls(
			check = lambda zanj, json_item, path: lh.check(json_item, path),
			load = lambda zanj, json_item, path: lh.load(json_item, path),
			desc = lh.desc,
		)

DEFAULT_LOADER_HANDLERS: tuple[LoaderHandler] = (
	LoaderHandler(
		check = lambda json_item, path: (
			isinstance(json_item, dict)
			and "__format__" in json_item
			and json_item["__format__"] == "array_list_meta"
		),
		load = lambda json_item, path: (
			np.array(json_item["data"], dtype=json_item["dtype"]).reshape(json_item["shape"])
		),
		desc = "array_list_meta loader",
	),
	LoaderHandler(
		check = lambda json_item, path: (
			isinstance(json_item, dict)
			and "__format__" in json_item
			and json_item["__format__"] == "array_hex_meta"
		),
		load = lambda json_item, path: (
			np.frombuffer(bytes.fromhex(json_item["data"]), dtype=json_item["dtype"]).reshape(json_item["shape"])
		),
		desc = "array_hex_meta loader",
	),
)


DEFAULT_LOADER_HANDLERS_ZANJ: tuple[ZANJLoaderHandler] = (
	ZANJLoaderHandler(
		check = lambda zanj, json_item, path: (
			isinstance(json_item, dict)
			and "__format__" in json_item
			and json_item["__format__"].startswith("external:")
		),
		load = lambda zanj, json_item, path: (
			zanj._externals[json_item["key"]]
		)
	),
) + tuple(
	ZANJLoaderHandler.from_LoaderHandler(lh) 
	for lh in DEFAULT_LOADER_HANDLERS
)




@dataclass
class ZANJLoaderTreeNode(typing.Mapping):
	"""acts like a regular dictionary or list, but applies loaders to items
	
	does this by passing `_parent` down the stack, whenever you get an item from the container.
	"""
	_parent: "LoadedZANJ"
	_data: dict[str, JSONitem]|list[JSONitem]

	def __getitem__(self, key: str|int) -> Any:
		# get value, check key types
		val: JSONitem
		if (
				(isinstance(self._data, list) and isinstance(key, int))
				or (isinstance(self._data, dict) and isinstance(key, str))
			):
			val = self._data[key]
		else:
			raise KeyError(f"invalid key type {type(key) = }, {key = } for {self._data = } with {type(self._data) = }")

		# get value or dereference
		if key == "$ref":
			val = self._parent._externals[val]
		else:
			val = self._data[key]

		if isinstance(val, (dict,list)):
			return ZANJLoaderTreeNode(_parent=self._parent, _data=val)
		else:
			return val

	def __iter__(self):
		return iter(self._data)
	
	def __len__(self):
		return len(self._data)


class LazyExternalLoader:
	"""lazy load np arrays or jsonl files, similar tp NpzFile from np.lib
	
	initialize with zipfile object and zanj metadata (for list of externals)
	"""

	def __init__(
			self,
			zipf: zipfile.ZipFile,
			zanj_meta: JSONitem,
			loaded_zanj: "LoadedZANJ",
		):
		self._zipf: zipfile.ZipFile = zipf
		self._zanj_meta: JSONitem = zanj_meta
		# (path, item_type) pairs
		self._externals_types: dict[str, str] = {
			key : val.item_type
			for key, val in zanj_meta["externals_info"].items()
		}

		# validate by checking each external file exists
		for key, item_type in self._externals_types.items():
			fname: str = f"{key}.{EXTERNAL_ITEMS_EXTENSIONS[item_type]}"
			if fname not in zipf.namelist():
				raise ValueError(f"external file {fname} not found in archive")


	def __getitem__(self, key: str) -> Any:
		if key in self._externals_types:
			path, item_type = key
			with self._zipf.open(path, "r") as fp:
				return EXTERNAL_LOAD_FUNCS[item_type](loaded_zanj, fp)



class LoadedZANJ(typing.Mapping):
	"""object loaded from ZANJ archive. acts like a dict."""
	def __init__(
		self,
		# config
		path: str|Path,
		zanj: "ZANJ",
		loader_handlers: MonoTuple[ZANJLoaderHandler],
		externals_mode: ExternalsLoadingMode = "lazy",
	) -> None:

		self._path: str = str(path)
		self._zanj: "ZANJ" = zanj
		self._externals_mode: ExternalsLoadingMode = externals_mode

		self._zipf: zipfile.ZipFile = zipfile.ZipFile(file=self._path, mode="r")

		self._meta: JSONitem = json.load(self._zipf.open(ZANJ_META, "r"))
		self._json_data: ZANJLoaderTreeNode = ZANJLoaderTreeNode(
			_parent = self,
			_data = json.load(self._zipf.open(ZANJ_MAIN, "r"))
		)

		self._externals: LazyExternalLoader|dict
		if externals_mode == "lazy":
			self._externals = LazyExternalLoader(
				zipf=self._zipf,
				zanj_meta=self._meta,
			)
		elif externals_mode == "full":
			self._externals = dict()
			
			for fname, val in self._meta["externals_info"].items():
				item_type: str = val["item_type"]
				with self._zipf.open(fname, "r") as fp:
					self._externals[fname] = EXTERNAL_LOAD_FUNCS[item_type](self, fp)
	
	def __getitem__(self, key: str) -> Any:
		"""get the value of the given key"""
		return self._json_data[key]
	
	def __iter__(self):
		return iter(self._json_data)
	
	def __len__(self):
		return len(self._json_data)