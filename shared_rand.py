"""
This file helps keep random seeding between different python files.
It just exports a shared seeded Random instance.
"""

from random import Random
rand: Random = Random(1234)