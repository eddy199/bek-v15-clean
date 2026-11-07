import urllib.request
import os

url = "https://raw.githubusercontent.com/eddy199/bek-v15-clean/main/README.md"
urllib.request.urlretrieve(url, "README.md")
print("OK - README.md a ete telecharge depuis GitHub")

# Ensuite on va le corriger si besoin (mais normalement il est bon)