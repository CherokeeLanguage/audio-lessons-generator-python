# Syllabary Lookup

A table of pronunciation to Syllabary mappings. `CSV` was chosen to simplify editing.

The file `lookup.csv` is regenerated each run of `syllabary_lookup.py` and should not be edited.

Place your desired edits in `user_fixes.csv` where the `user` in `user_fixes.csv` is your handle. For example: ᎹᎦᎵ's file would be named `magali_fixes.csv`. Please use your own file. Use the same format as the main `lookup.csv` file.

If the first field in a row contains a "*" then the pronunciation to Syllabary is incomplete for that entry and it needs a fix added to your fixes file.

When the `syllabary_lookup.py` program is run, it will overwrite any entries from the main `lookup.csv` file with fixes supplied by the various `*_fixes.csv` files then write out the
corrected file.

The `lookup.csv` file is periodically committed by ᎹᎦᎵ to reflect any new entries that need fixing.

**NOTE**:

Running the `syllabary_lookup.py` script will rewrite all the Syllabary entries in the dataset files.
