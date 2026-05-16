# JSON Glance

*See the shape of any JSON or nested data at a glance.*

[![PyPI](https://img.shields.io/pypi/v/json-glance)](https://pypi.org/project/json-glance/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)

You get a JSON blob - an API response, a webhook payload, a `.jsonl` export - and
your first question is always *"what does this thing even look like?"* JSON Glance
answers it in one call: it walks the data and prints a compact summary of its
*shape* - types, nesting, sizes, value ranges, and null rates - so you stop
scrolling through raw JSON to find out.

Think `df.describe()`, but for nested data instead of tables. Zero dependencies,
pure standard library, Python 3.9+.

## What it shows

- **Merged shapes** - every dict in an array is folded into a single schema, so
  a long list of records prints as one shape instead of one block per element.
- **Honest denominators** - a key absent from a record and a key present with a
  null value are reported as two distinct facts, never conflated.
- **Type unions** - when a field holds more than one type, every type observed
  is listed with the share of values that took it.
- **Value stats** - numeric ranges, string-length ranges, boolean true-rates,
  and collection sizes.
- **Pattern hints** - common string formats such as UUIDs, emails, and
  timestamps are flagged, but only when every value at that position matches.
- **Map detection** - a dict used as a key-value store is summarized as a map
  rather than dumped as a giant record.
- **Safe on anything** - it never recurses into an object's internals or calls
  your code; non-JSON values are reported by type name, and cyclic structures
  are detected instead of causing a hang.

## Install

```bash
pip install json-glance
```

## Usage

### Python

```python
from json_glance import glance, summary

glance(data)            # print the shape summary to stdout
text = summary(data)    # ...or capture it as a string (logs, tests, notebooks)
glance(data, depth=3)   # limit how many levels deep it descends
```

### Command line

```bash
json-glance response.json          # summarize a JSON file
json-glance events.jsonl           # newline-delimited JSON, all records merged
curl -s https://api.example.com/x | json-glance   # or straight from a pipe
```

## Example

Run it on a typical paginated API response (`examples/api_response.json` - three
users, with pagination metadata):

```text
$ json-glance examples/api_response.json
dict  · 5 keys
├─ users        list  · 3 items
│  └─ dict  · 9 keys
│     ├─ id              str   len 36  ~uuid
│     ├─ email           str   len 15 – 17  ~email
│     ├─ name            str   len 12 – 14
│     ├─ role            str   len 4 – 5
│     ├─ verified        bool  67% true
│     ├─ created_at      str   len 20  ~datetime
│     ├─ login_count     int   5 – 342
│     ├─ profile         dict  · 2 keys
│     │  ├─ city      str  len 6 – 8
│     │  └─ timezone  str  len 13 – 19
│     └─ deactivated_at  null  (67% missing)
├─ page         int   = 1
├─ per_page     int   = 20
├─ total        int   = 3
└─ next_cursor  null
```

The three user records were merged into one shape. At a glance: `id` always
looks like a UUID and `email` always like an email, `created_at` is always a
timestamp, `verified` is true for two of three users, `login_count` ranges
5-342, and `deactivated_at` is set on only one user (so 67% missing). A
1,000-user response would print the exact same shape - just with bigger numbers.

## API

| Function | Returns | Description |
|---|---|---|
| `glance(data, *, depth=6, max_keys=50, file=None)` | `None` | prints the summary |
| `summary(data, *, depth=6, max_keys=50)` | `str` | returns the summary as a string |

- `depth` - nesting levels to show before collapsing to `…`.
- `max_keys` - record keys to show before `+N more`.

## License

MIT.
