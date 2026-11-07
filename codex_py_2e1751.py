import subprocess
import sys

try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "setuptools", "wheel"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pygame"])
    print("pygame installé avec succès.")
except subprocess.CalledProcessError as e:
    print(f"Erreur lors de l'installation : {e}")