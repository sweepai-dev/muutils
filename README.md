

`muutils`, stylized as "$\mu$utils" or "μutils", is a collection of miscellaneous python utilities, meant to be small and with ~~no~~ minimal dependencies outside of standard python.


- [`json_serialize`](https://github.com/mivanit/muutils/tree/main/muutils/json_serialize.py) is a tool for serializing and loading arbitrary python objects into json. plays nicely with [`ZANJ`](https://github.com/mivanit/ZANJ/)
- [`statcounter`](https://github.com/mivanit/muutils/tree/main/muutils/statcounter.py) is an extension of `collections.Counter` that provides "smart" computation of stats (mean, variance, median, other percentiles) from the counter object without using `Counter.elements()`
- `misc` contains a few utilities:
	- `stable_hash()` uses `hashlib.sha256` to compute a hash of an object that is stable across runs of python
	- `sanitize_fname()` takes any string and makes it only alphanumeric plus `-` and `_`
	- `shorten_numerical_to_str()` turns numbers like `123456789` into `"123M"`
	- a couple other things
- [`nbutils`] (WIP) contains some utilities for working in notebooks (printing latex nicely) and also running notebooks as tests in CI by converting them to python scripts
- [`tensor_utils`] contains minor utilities for working with pytorch tensors and numpy arrays. This needs to be moved into ZANJ, probably
- [`group_equiv`](https://github.com/mivanit/muutils/tree/main/muutils/group_equiv.py) groups elements from a sequence according to a given equivalence relation, without assuming that the equivalence relation obeys the transitive property
- [`logger`](https://github.com/mivanit/muutils/tree/main/muutils/logger.py) implements a logger with "streams" and a timer context manager
- [`jsonlines`](https://github.com/mivanit/muutils/tree/main/muutils/jsonlines.py) extremely simple utility for reading/writing `jsonl` files
- [`ZANJ`](https://github.com/mivanit/ZANJ/) is a WIP hdf5 alternative. This ~~will probably be~~ has been spun off into its own repo

There are a couple work-in-progress utilities in [`_wip`](https://github.com/mivanit/muutils/tree/main/muutils/_wip/) that aren't ready for anything, but nothing in this repo is suitable for production. Use at your own risk!


# installation

```
pip install muutils
```
