"""
Just import this on the microcontroller command line (e.g.via Thonny) and all the
logs will be deleted

Example usage:
  >>> import cleanup_logs
  Deleted: 2023-9-26-5-44-15-traceback.log
  Deleted: 2023-9-26-9-44-51-traceback.log
  Deleted: 2023-9-27-1-48-55-traceback.log
  >>>
"""
import os

file_extension_pattern = '.log'
try:
    # List all files in the directory
    files = os.listdir()
    # Iterate through the files and delete those that match the pattern
    for file in files:
        if file.endswith(file_extension_pattern):
            os.remove(file)
            print(f"Deleted: {file}")
except OSError as e:
    print(f"Error: {e}")
