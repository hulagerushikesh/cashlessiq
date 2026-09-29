"""Compatibility entry point for the seeded Faker generator.

Synthea is deliberately not used by the MVP; the filename remains because it is
part of the agreed repository layout.
"""

from data_gen.generate import main

if __name__ == "__main__":
    main()
