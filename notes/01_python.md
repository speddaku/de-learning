# Python — Complete Notes from Scratch

---

## 1. Variables & Data Types

Python is dynamically typed, but understanding type coercion rules matters when processing messy data — a string `"42"` and an integer `42` will silently behave differently in comparisons and arithmetic.

```python
# Integers
x = 10
y = -5
big = 1_000_000        # underscore for readability

# Floats
pi = 3.14159
sci = 1.5e10           # scientific notation

# Strings
name = "Suhas"
multi = """Line 1
Line 2"""

# Boolean
is_active = True
is_done = False

# None
result = None

# Type checking
type(x)        # <class 'int'>
isinstance(x, int)  # True

# Type casting
int("42")      # 42
float("3.14")  # 3.14
str(100)       # "100"
bool(0)        # False — 0, "", [], {}, None are all Falsy
```

> **💡 Interview tip:** Interviewers love asking about truthiness. `bool([])` is `False`, `bool([0])` is `True` (non-empty list). Relevant in DE when checking if a result set is empty: `if df:` on a DataFrame raises an error — use `if df.empty:` instead.

---

## 2. Strings

String manipulation is constant in DE — parsing filenames, cleaning column headers, extracting date parts from messy CSVs. Python's string methods are the first line of defense before data hits your pipeline.

```python
s = "Hello, World!"

# Indexing & Slicing
s[0]        # 'H'
s[-1]       # '!'
s[0:5]      # 'Hello'
s[::2]      # every 2nd char
s[::-1]     # reverse

# Methods
s.upper()           # 'HELLO, WORLD!'
s.lower()           # 'hello, world!'
s.strip()           # remove whitespace
s.lstrip("H")       # remove from left
s.split(", ")       # ['Hello', 'World!']
s.replace("World", "Suhas")
s.startswith("Hello")   # True
s.endswith("!")         # True
s.find("World")         # 7 — index, -1 if not found
s.count("l")            # 3
",".join(["a","b","c"]) # 'a,b,c'

# Formatting
name = "Suhas"
age = 30
f"My name is {name} and I am {age}"   # f-string (preferred)
"My name is {} and I am {}".format(name, age)
"%.2f" % 3.14159   # '3.14'

# String is immutable
# s[0] = 'h'  → TypeError
```

> **🌍 Real world:** In ETL, always `.strip().lower()` incoming string keys before joining — source systems frequently have trailing spaces or inconsistent casing that cause silent row drops on joins.

---

## 3. Lists

Lists are your in-memory workhorse for small to medium datasets. When a dataset is small enough to fit in memory, a list comprehension is often 2–3x faster to write and execute than a full pandas DataFrame operation.

```python
lst = [1, 2, 3, 4, 5]

# Access
lst[0]       # 1
lst[-1]      # 5
lst[1:3]     # [2, 3]

# Modify
lst.append(6)          # [1,2,3,4,5,6]
lst.insert(0, 0)       # insert at index
lst.extend([7, 8])     # add multiple
lst.pop()              # remove & return last
lst.pop(0)             # remove & return at index
lst.remove(3)          # remove first occurrence of value
del lst[0]             # delete by index

# Info
len(lst)
lst.index(4)           # first index of value
lst.count(2)           # count occurrences
4 in lst               # True

# Sorting
lst.sort()             # in-place, ascending
lst.sort(reverse=True)
sorted(lst)            # returns new list
lst.sort(key=lambda x: -x)  # sort by key

# Copy
lst2 = lst.copy()      # shallow copy
lst2 = lst[:]          # also shallow copy
import copy
lst3 = copy.deepcopy(lst)  # deep copy

# List comprehension
squares = [x**2 for x in range(10)]
evens = [x for x in range(20) if x % 2 == 0]
flat = [item for sublist in [[1,2],[3,4]] for item in sublist]
```

> **💡 Interview tip:** Shallow copy vs deep copy is a classic trap. `lst2 = lst` is a reference (modifying one modifies the other). `lst.copy()` copies the outer list but nested objects are still shared. `deepcopy` recursively copies everything. In DE, this matters when you're building multiple DataFrame variants from the same base dict config.

---

## 4. Tuples

Think of tuples as "records" — they represent a fixed structure where position has semantic meaning, like a database row. Using a tuple as a dict key (e.g., `(customer_id, date)`) is a common pattern when building in-memory lookup tables during ETL.

```python
t = (1, 2, 3)
t2 = 1, 2, 3       # parentheses optional
single = (1,)       # trailing comma required for single element

# Tuples are IMMUTABLE — can't modify after creation
# Use when data shouldn't change: coordinates, DB rows, dict keys

t[0]                # 1
len(t)              # 3
a, b, c = t         # unpacking
first, *rest = t    # star unpacking → first=1, rest=[2,3]

# Named tuple
from collections import namedtuple
Point = namedtuple('Point', ['x', 'y'])
p = Point(3, 4)
p.x    # 3
```

> **🌍 Real world:** `namedtuple` is useful when returning multiple values from a function — it's self-documenting and prevents the "what does index 2 mean?" confusion that plagues raw tuple returns from complex transformation functions.

---

## 5. Sets

Sets give you O(1) membership testing — the same asymptotic complexity as a hash table. When you need to check "has this record ID already been processed?" across millions of IDs, a set beats a list by orders of magnitude.

```python
s = {1, 2, 3, 4}
s2 = set([1, 2, 2, 3])   # {1, 2, 3} — duplicates removed

# No duplicates, unordered, no indexing
s.add(5)
s.remove(3)        # KeyError if not found
s.discard(10)      # no error if not found

# Set operations
a = {1, 2, 3}
b = {2, 3, 4}
a | b              # union {1,2,3,4}
a & b              # intersection {2,3}
a - b              # difference {1}
a ^ b              # symmetric difference {1,4}
a.issubset(b)
a.issuperset(b)

# Use case: deduplication, membership testing (O(1) lookup)
```

> **💡 Interview tip:** Set difference (`a - b`) is the idiomatic way to find "records in source but not in target" during reconciliation — a common DE task when comparing a staging load against an existing table.

---

## 6. Dictionaries

Dictionaries are the backbone of in-memory data transformation. In DE, you'll use them constantly for config objects, lookup tables (mapping product_id → product_name), and accumulating counts/aggregates before writing to a sink.

```python
d = {"name": "Suhas", "age": 30, "city": "Vancouver"}

# Access
d["name"]               # 'Suhas'
d.get("salary", 0)      # 0 if key missing (safe)

# Modify
d["age"] = 31
d["country"] = "Canada"
del d["city"]
d.pop("age")            # remove and return

# Info
d.keys()
d.values()
d.items()               # list of (key, value) tuples
"name" in d             # True

# Merge (Python 3.9+)
d3 = d | {"extra": "val"}

# Dict comprehension
squares = {x: x**2 for x in range(5)}

# Nested dict
config = {
    "db": {"host": "localhost", "port": 5432},
    "cache": {"host": "localhost", "port": 6379}
}
config["db"]["host"]    # 'localhost'

# defaultdict
from collections import defaultdict
word_count = defaultdict(int)
for word in ["a", "b", "a"]:
    word_count[word] += 1

# OrderedDict (Python 3.7+ regular dicts maintain insertion order)
from collections import OrderedDict

# Counter
from collections import Counter
c = Counter(["a", "b", "a", "c", "a"])
c.most_common(2)   # [('a', 3), ('b', 1)]
```

> **🌍 Real world:** `defaultdict(list)` is a classic pattern for grouping records: `groups[key].append(record)` without needing to check if the key exists first. Used extensively when building dimension lookup tables from flat files.

---

## 7. Conditionals & Loops

```python
# if/elif/else
x = 10
if x > 0:
    print("positive")
elif x == 0:
    print("zero")
else:
    print("negative")

# Ternary
result = "even" if x % 2 == 0 else "odd"

# for loop
for i in range(5):          # 0,1,2,3,4
    print(i)

for i in range(2, 10, 2):   # start, stop, step
    print(i)

for item in ["a", "b", "c"]:
    print(item)

for i, item in enumerate(["a", "b", "c"]):
    print(i, item)

for k, v in d.items():
    print(k, v)

# zip
for a, b in zip([1,2,3], ["x","y","z"]):
    print(a, b)

# while loop
n = 0
while n < 5:
    n += 1

# break, continue, pass
for i in range(10):
    if i == 3: continue    # skip
    if i == 7: break       # exit loop
    pass                   # do nothing placeholder
```

---

## 8. Functions

The choice between a standalone function and a class method in DE often comes down to state: if the logic is purely transformational (input → output, no side effects), a function is simpler. If you need to maintain state across calls (connection pooling, batching, retries with backoff), reach for a class.

```python
# Basic
def greet(name):
    return f"Hello, {name}"

# Default arguments
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}"

# *args — variable positional arguments
def add(*nums):
    return sum(nums)
add(1, 2, 3)    # 6

# **kwargs — variable keyword arguments
def display(**info):
    for k, v in info.items():
        print(f"{k}: {v}")
display(name="Suhas", age=30)

# Type hints
def process(data: list[int], multiplier: float = 1.0) -> list[float]:
    return [x * multiplier for x in data]

# Lambda
square = lambda x: x ** 2
add = lambda x, y: x + y

# First-class functions
def apply(func, value):
    return func(value)
apply(square, 5)   # 25

# Nested functions & closures
def multiplier(n):
    def multiply(x):
        return x * n      # captures n from outer scope
    return multiply

double = multiplier(2)
double(5)   # 10

# Docstrings
def calculate(x: int, y: int) -> int:
    """Add two numbers and return result."""
    return x + y
```

> **💡 Interview tip:** When asked "functions vs classes in DE" — the answer is closures/functions for simple stateless transforms, classes for anything that needs to hold state (e.g., a `DatabaseLoader` class that maintains a connection pool and tracks batch counts). Interviewers want to hear you think about lifecycle management.

---

## 9. Error Handling

In production pipelines, swallowing errors silently is the cardinal sin. The difference between `except Exception` (log and move on) vs re-raising (`raise`) is a design decision about pipeline fault tolerance — partial failures vs fail-fast.

```python
# try/except/else/finally
try:
    result = 10 / 0
except ZeroDivisionError as e:
    print(f"Error: {e}")
except (TypeError, ValueError) as e:
    print(f"Type or Value error: {e}")
except Exception as e:
    print(f"Unexpected: {e}")
else:
    print("No error!")         # runs if no exception
finally:
    print("Always runs")       # cleanup — always runs

# Raise exceptions
def divide(a, b):
    if b == 0:
        raise ValueError("b cannot be zero")
    return a / b

# Custom exceptions
class DataValidationError(Exception):
    def __init__(self, field, message):
        self.field = field
        super().__init__(f"{field}: {message}")

raise DataValidationError("age", "must be positive")

# Context: use specific exceptions, not bare except
# Don't: except:
# Do:    except ValueError:
```

> **🌍 Real world:** In Airflow/Glue pipelines, `finally` blocks are your safety net for closing database connections, flushing buffers, and releasing locks — regardless of whether the task succeeded or failed. Skipping `finally` is how you leak connections in long-running workers.

---

## 10. File I/O

```python
# Write
with open("file.txt", "w") as f:
    f.write("Hello\n")
    f.writelines(["Line 1\n", "Line 2\n"])

# Read
with open("file.txt", "r") as f:
    content = f.read()          # entire file as string
    lines = f.readlines()       # list of lines

# Append
with open("file.txt", "a") as f:
    f.write("New line\n")

# CSV
import csv
with open("data.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row["name"])

with open("out.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["name", "age"])
    writer.writeheader()
    writer.writerow({"name": "Suhas", "age": 30})

# JSON
import json
data = {"name": "Suhas", "skills": ["Python", "SQL"]}
json_str = json.dumps(data, indent=2)    # dict → string
data2 = json.loads(json_str)             # string → dict

with open("data.json", "w") as f:
    json.dump(data, f, indent=2)

with open("data.json") as f:
    data = json.load(f)

# Paths
from pathlib import Path
p = Path("/Users/saisuhas/data")
p.exists()
p.mkdir(parents=True, exist_ok=True)
p / "file.txt"                  # path joining
list(p.glob("*.csv"))           # find files
```

> **💡 Interview tip:** `pathlib.Path` over `os.path` is the modern answer. Path objects are composable (`base_path / "subdir" / "file.csv"`) and platform-agnostic. In cloud DE contexts, this matters for local testing vs S3-path abstractions.

---

## 11. OOP — Object-Oriented Programming

Classes shine in DE when you're modeling something that has both state and behavior. A pipeline class that tracks run status, handles retries, and maintains a connection is a natural fit. A pure function that maps one record schema to another is not — keep that a function.

```python
# Class definition
class DataPipeline:
    # Class variable (shared across all instances)
    pipeline_count = 0

    def __init__(self, name: str, source: str):
        # Instance variables
        self.name = name
        self.source = source
        self._status = "idle"          # _ = convention for "private"
        DataPipeline.pipeline_count += 1

    # Instance method
    def run(self):
        self._status = "running"
        print(f"Running pipeline: {self.name}")

    # Property — getter
    @property
    def status(self):
        return self._status

    # Property — setter
    @status.setter
    def status(self, value):
        if value not in ("idle", "running", "failed", "done"):
            raise ValueError(f"Invalid status: {value}")
        self._status = value

    # Class method
    @classmethod
    def get_count(cls):
        return cls.pipeline_count

    # Static method — no access to self or cls
    @staticmethod
    def validate_name(name: str) -> bool:
        return len(name) > 0

    # String representation
    def __repr__(self):
        return f"DataPipeline(name={self.name!r}, source={self.source!r})"

    def __str__(self):
        return f"Pipeline: {self.name}"


# Inheritance
class GluePipeline(DataPipeline):
    def __init__(self, name: str, source: str, job_name: str):
        super().__init__(name, source)   # call parent __init__
        self.job_name = job_name

    def run(self):
        print(f"Starting Glue job: {self.job_name}")
        super().run()                    # call parent method


# Abstract classes
from abc import ABC, abstractmethod

class BaseTool(ABC):
    @abstractmethod
    def execute(self) -> str:
        """Every subclass must implement this."""
        ...

    def log(self, msg):
        print(f"[{self.__class__.__name__}] {msg}")


class WebTool(BaseTool):
    def execute(self) -> str:
        return "web result"


# Dunder/magic methods
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):      # v1 + v2
        return Vector(self.x + other.x, self.y + other.y)

    def __len__(self):             # len(v)
        return 2

    def __eq__(self, other):       # v1 == v2
        return self.x == other.x and self.y == other.y

    def __repr__(self):
        return f"Vector({self.x}, {self.y})"
```

> **💡 Interview tip:** `@classmethod` vs `@staticmethod` is a common question. The real-world distinction: use `@classmethod` as an alternative constructor (e.g., `Pipeline.from_config(config_dict)`) — it has access to `cls` so subclasses can override it correctly. Use `@staticmethod` for pure utility logic that conceptually belongs to the class but doesn't need class state.

---

## 12. Decorators

A decorator is a function that wraps another function — think of it as middleware. It intercepts the call, can add behavior before and after execution, and passes through the result. In DE this pattern is ubiquitous for cross-cutting concerns: retry logic, logging, timing, and metric emission without polluting business logic.

```python
# A decorator wraps a function to add behaviour
import functools
import time

# Basic decorator
def timer(func):
    @functools.wraps(func)          # preserves function metadata
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.time()-start:.2f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)

# Decorator with arguments
def retry(times=3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == times - 1:
                        raise
                    print(f"Attempt {attempt+1} failed: {e}")
        return wrapper
    return decorator

@retry(times=3)
def unstable_api_call():
    ...
```

> **💡 Interview tip:** Always use `@functools.wraps(func)` inside your decorator's wrapper. Without it, the wrapped function loses its `__name__` and `__doc__`, which breaks introspection, logging, and pytest. This is a subtle but frequently tested gotcha.

> **🌍 Real world:** The `retry` decorator pattern with exponential backoff is standard practice for API-based data ingestion — rate limits, transient 5xx errors, and network blips are the norm, not the exception. Libraries like `tenacity` implement this more robustly, but understanding the decorator pattern behind it is expected in interviews.

---

## 13. Generators & Iterators

Generators are the most important memory-efficiency tool in Python for DE. Here's the core insight: a list comprehension like `[x**2 for x in range(1_000_000)]` allocates all 1 million integers in memory at once. A generator expression `(x**2 for x in range(1_000_000))` produces one value at a time — the memory footprint is O(1) regardless of dataset size.

Think of it like a water tap vs a water tank: a tank holds all the water upfront; a tap delivers it on demand.

```python
# Iterator protocol
class CountUp:
    def __init__(self, max):
        self.max = max
        self.current = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.current >= self.max:
            raise StopIteration
        self.current += 1
        return self.current

for n in CountUp(5):
    print(n)   # 1 2 3 4 5

# Generator function — uses yield
def count_up(max):
    current = 0
    while current < max:
        current += 1
        yield current           # pauses here, resumes on next()

gen = count_up(5)
next(gen)   # 1
next(gen)   # 2

for n in count_up(5):
    print(n)

# Generator expression (like list comprehension but lazy)
gen = (x**2 for x in range(1000000))   # doesn't create list in memory
next(gen)   # 0

# Why generators?
# - Memory efficient — generates values on demand
# - Great for large files, streaming data

# Reading large files with generator
def read_large_file(path):
    with open(path) as f:
        for line in f:
            yield line.strip()

# yield from
def chain(*iterables):
    for it in iterables:
        yield from it
```

> **💡 Interview tip:** The classic interview question is "how would you process a 100GB log file in Python without running out of memory?" The answer is a generator that yields one line at a time — the file object itself is already an iterator in Python, so `for line in f:` is inherently lazy. The wrong answer is `f.readlines()` (loads everything into memory) or `f.read()`.

> **🌍 Real world:** Generator pipelines — chaining multiple generators together — are the Python equivalent of Unix pipes. Each stage processes one record at a time, memory stays flat, and you get natural backpressure. This pattern maps directly to how Spark and other streaming frameworks think about data processing.

---

## 14. Context Managers

Context managers enforce the "acquire, use, release" lifecycle pattern. The guarantee is strong: even if an exception occurs inside the `with` block, `__exit__` (or the `finally` in `@contextmanager`) will run. This is critical for database connections, file handles, and distributed locks.

```python
# The 'with' statement ensures cleanup happens
# Even if an exception is raised

# Using contextlib
from contextlib import contextmanager

@contextmanager
def managed_resource(name):
    print(f"Acquiring {name}")
    try:
        yield name              # code inside 'with' block runs here
    finally:
        print(f"Releasing {name}")   # always runs

with managed_resource("DB connection") as conn:
    print(f"Using {conn}")

# Class-based context manager
class DatabaseConnection:
    def __init__(self, url):
        self.url = url

    def __enter__(self):
        print(f"Connecting to {self.url}")
        self.conn = "fake_connection"
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Closing connection")
        self.conn = None
        return False    # False = don't suppress exceptions

with DatabaseConnection("postgresql://localhost/db") as conn:
    # use conn here
    pass
```

> **💡 Interview tip:** `__exit__` receives exception info as arguments. Returning `True` suppresses the exception (swallows it); returning `False` or `None` lets it propagate. You almost always want `False` — suppressing exceptions silently is how bugs disappear into the void.

---

## 15. List/Dict/Set Comprehensions

Comprehensions are more Pythonic than explicit loops, and they also tend to be faster because the interpreter optimizes the iteration internally. The rule of thumb: if a comprehension requires more than two conditions or nested logic beyond two levels, a regular loop is more readable.

```python
# List comprehension
squares = [x**2 for x in range(10)]
evens = [x for x in range(20) if x % 2 == 0]
pairs = [(x, y) for x in range(3) for y in range(3)]

# Dict comprehension
word_len = {word: len(word) for word in ["python", "sql", "spark"]}
inverted = {v: k for k, v in {"a": 1, "b": 2}.items()}

# Set comprehension
unique_lengths = {len(word) for word in ["hi", "hello", "hey"]}

# Nested comprehension
matrix = [[1,2,3],[4,5,6],[7,8,9]]
flat = [n for row in matrix for n in row]

# Conditional expression (ternary)
result = [x if x > 0 else 0 for x in [-1, 2, -3, 4]]
```

> **🌍 Real world:** Dict comprehensions for schema mapping are a DE staple: `{old_name: new_name for old_name, new_name in zip(source_columns, target_columns)}`. Much cleaner than a for loop when renaming 30 columns from a source schema.

---

## 16. Map, Filter, Reduce

```python
from functools import reduce

nums = [1, 2, 3, 4, 5]

# map — apply function to each element
doubled = list(map(lambda x: x*2, nums))
# equivalent: [x*2 for x in nums]

# filter — keep elements where function returns True
evens = list(filter(lambda x: x%2==0, nums))
# equivalent: [x for x in nums if x%2==0]

# reduce — accumulate to single value
total = reduce(lambda acc, x: acc + x, nums)   # 15
product = reduce(lambda acc, x: acc * x, nums, 1)  # 120

# In practice, list comprehensions and sum/any/all are preferred
total = sum(nums)
any(x > 4 for x in nums)   # True
all(x > 0 for x in nums)   # True
```

> **💡 Interview tip:** `map` and `filter` return lazy iterators in Python 3, not lists. If you need a list immediately, wrap in `list()`. But often in a pipeline context, passing the lazy iterator to the next stage is exactly what you want.

---

## 17. Modules & Packages

```python
# Import
import os
import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import Optional, List, Dict, Tuple, Any, Union

# Relative imports (within a package)
# from . import sibling_module
# from ..parent import something

# __name__ == "__main__"
if __name__ == "__main__":
    # Only runs when script is executed directly
    # Not when imported as module
    main()

# Package structure
# my_package/
#   __init__.py
#   module_a.py
#   subpackage/
#     __init__.py
#     module_b.py
```

---

## 18. Type Hints

Type hints don't affect runtime behavior — Python doesn't enforce them at execution time. Their value is tooling and communication: mypy/pyright catch type mismatches statically, IDEs autocomplete correctly, and future teammates understand what a function expects without reading its implementation. In a team DE codebase with dozens of transformation functions, this is the difference between "readable, maintainable code" and "tribal knowledge hell."

```python
from typing import Optional, List, Dict, Tuple, Any, Union
from typing import Callable, Generator, Iterator

def process(
    data: list[dict],
    limit: int = 100,
    callback: Optional[Callable] = None
) -> list[str]:
    ...

# Python 3.10+ union type
def greet(name: str | None) -> str:
    ...

# TypedDict
from typing import TypedDict

class UserRecord(TypedDict):
    id: int
    name: str
    email: str

# Pydantic for runtime validation
from pydantic import BaseModel, Field

class PipelineConfig(BaseModel):
    name: str
    source: str
    batch_size: int = Field(default=1000, gt=0)
    enabled: bool = True

config = PipelineConfig(name="test", source="s3://bucket")
config.batch_size   # 1000
```

> **💡 Interview tip:** The distinction between `TypedDict` and Pydantic is worth knowing. `TypedDict` is pure type-checker annotation — no runtime validation. Pydantic validates at instantiation time and raises errors with useful messages. For pipeline configs loaded from YAML/JSON, Pydantic is the safer choice because it fails loudly with a clear message rather than silently passing through a bad config.

> **🌍 Real world:** In larger DE platforms, Pydantic models for pipeline configuration serve as the contract between the platform team (who builds the orchestration infra) and the data team (who writes the business logic). A well-typed config model prevents the "it ran but produced garbage because batch_size was a string" class of errors.

---

## 19. Pandas

Pandas is powerful but has several performance traps that bite even experienced engineers. The core mental model: pandas operations that return a new DataFrame are generally efficient; operations that iterate row-by-row in Python (`.apply` with a Python lambda, `.iterrows()`) are slow because they bypass the vectorized C/Cython internals.

```python
import pandas as pd
import numpy as np

# Create DataFrame
df = pd.DataFrame({
    "name": ["Alice", "Bob", "Charlie"],
    "age": [25, 30, 35],
    "salary": [50000, 60000, 70000]
})

# Read/Write
df = pd.read_csv("data.csv")
df = pd.read_parquet("data.parquet")
df = pd.read_json("data.json")
df.to_csv("out.csv", index=False)
df.to_parquet("out.parquet")

# Inspection
df.shape          # (rows, cols)
df.dtypes
df.info()
df.describe()
df.head(5)
df.tail(5)

# Selection
df["name"]                    # Series
df[["name", "age"]]           # DataFrame
df.loc[0]                     # by label
df.iloc[0]                    # by position
df.loc[df["age"] > 28]        # boolean filter
df.query("age > 28")          # query string

# Operations
df["salary_k"] = df["salary"] / 1000    # new column
df.rename(columns={"name": "full_name"})
df.drop(columns=["age"])
df.drop_duplicates()
df.fillna(0)
df.dropna()
df["age"].astype(float)

# GroupBy
df.groupby("dept")["salary"].mean()
df.groupby("dept").agg({"salary": ["mean", "max"], "age": "count"})

# Merge/Join
merged = pd.merge(df1, df2, on="id", how="left")
pd.concat([df1, df2], ignore_index=True)

# Apply
df["name_upper"] = df["name"].apply(lambda x: x.upper())
df.apply(lambda row: row["age"] * 2, axis=1)

# Pivot
pivot = df.pivot_table(values="salary", index="dept", columns="role", aggfunc="mean")

# Sort
df.sort_values("salary", ascending=False)

# String operations
df["name"].str.lower()
df["name"].str.contains("Al")
df["name"].str.split(" ")
```

> **💡 Interview tip:** Performance gotchas that come up in interviews:
> 1. `.apply()` with a Python function is row-by-row — use vectorized operations (`df["col"] * 2`) or `.str` methods when possible. Can be 10–100x slower.
> 2. Chained assignment (`df["a"]["b"] = value`) raises `SettingWithCopyWarning` and may not work — always use `.loc[row_indexer, col_indexer]`.
> 3. `df.iterrows()` is the slowest way to iterate — 100x slower than `.apply()`. Use it only when absolutely necessary.
> 4. Reading a CSV with string columns that should be numeric silently stores them as `object` dtype — always check `df.dtypes` after loading.

> **🌍 Real world:** For truly large datasets (>1GB), pandas in-memory processing hits its limits. The progression is: pandas → pandas with chunking (`read_csv(chunksize=...)`) → Dask → PySpark. Knowing where each tool hits its ceiling is a senior-level answer.

---

## 20. pytest

```python
# test_pipeline.py
import pytest
from my_module import add, DataPipeline

# Basic test
def test_add():
    assert add(2, 3) == 5

# Test exception
def test_add_strings():
    with pytest.raises(TypeError):
        add("a", 1)

# Fixtures — reusable setup
@pytest.fixture
def sample_pipeline():
    return DataPipeline(name="test", source="s3://bucket")

def test_pipeline_run(sample_pipeline):
    sample_pipeline.run()
    assert sample_pipeline.status == "running"

# Parametrize — run same test with different inputs
@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
])
def test_add_parametrized(a, b, expected):
    assert add(a, b) == expected

# Mocking
from unittest.mock import MagicMock, patch

def test_with_mock():
    with patch("my_module.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"status": "ok"}
        result = fetch_data("http://api.example.com")
        assert result["status"] == "ok"

# Run: pytest -v
# Run specific: pytest test_pipeline.py::test_add -v
# Coverage: pytest --cov=my_module
```

> **🌍 Real world:** In DE, the most valuable tests are not unit tests for individual functions — they're integration tests that validate the full transform: given this input schema and data, does the output match the expected schema and row count? Parametrize fixtures with representative edge cases: nulls, empty sets, duplicate keys, max/min values.

---

## Key Concepts Summary

| Concept | One-liner |
|---------|-----------|
| List vs Tuple | List = mutable, Tuple = immutable |
| List vs Set | Set = no duplicates, O(1) lookup |
| Dict vs defaultdict | defaultdict returns default on missing key |
| Generator | Yields values lazily — memory efficient |
| Decorator | Wraps function to add behaviour without changing it |
| Context Manager | Ensures setup/teardown with `with` statement |
| `*args` | Collects positional args as tuple |
| `**kwargs` | Collects keyword args as dict |
| `@classmethod` | Gets `cls` instead of `self`, can access class state |
| `@staticmethod` | No `self` or `cls`, pure utility function |
| `@property` | Makes method accessible like attribute |
