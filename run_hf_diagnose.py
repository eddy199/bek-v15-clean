import sys
import os
service_path = r'F:\workspacekimi\services'
if service_path not in sys.path:
    sys.path.append(service_path)

try:
    from huggingface_service import diagnose_hf_plugin
except ImportError as e:
    print(f"Erreur d'import : {e}")
    sys.exit(1)

if __name__ == '__main__':
    result = diagnose_hf_plugin()
    print(result)
