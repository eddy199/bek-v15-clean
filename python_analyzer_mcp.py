# python_analyzer_mcp.py
# Serveur MCP pour analyser du code Python source
import ast
import os
import sys
import json
import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Python-Analyzer")

# Dossier de sortie par défaut (F:\workspacekimi\generated)
GENERATED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")

@mcp.tool()
def analyze_python_file(file_path: str) -> str:
    """Analyse un fichier Python et retourne sa structure (classes, fonctions, imports)."""
    try:
        if not os.path.exists(file_path):
            return json.dumps({"status": "error", "message": f"Fichier introuvable : {file_path}"})

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        result = {
            "file": file_path,
            "lines": len(source.splitlines()),
            "imports": [],
            "classes": [],
            "functions": []
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                result["imports"].append(f"{node.module}.{node.names[0].name}")
            elif isinstance(node, ast.ClassDef):
                result["classes"].append({
                    "name": node.name,
                    "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                })
            elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                result["functions"].append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args]
                })

        return json.dumps({"status": "success", "analysis": result}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@mcp.tool()
def analyze_python_directory(dir_path: str) -> str:
    """Analyse tous les fichiers .py d'un dossier et détecte les anomalies."""
    try:
        if not os.path.isdir(dir_path):
            return json.dumps({"status": "error", "message": f"Dossier introuvable : {dir_path}"})

        results = []
        total_lines = 0
        warnings = []

        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    analysis = json.loads(analyze_python_file(file_path))
                    if analysis.get("status") == "success":
                        data = analysis["analysis"]
                        results.append(data)
                        total_lines += data["lines"]

                        # Détection d'anomalies
                        if data["lines"] > 300:
                            warnings.append(f"Fichier volumineux : {data['file']} ({data['lines']} lignes)")
                        for cls in data.get("classes", []):
                            if len(cls.get("methods", [])) > 20:
                                warnings.append(f"Classe avec trop de méthodes : {cls['name']} ({len(cls['methods'])} méthodes) dans {data['file']}")

        return json.dumps({
            "status": "success",
            "files_analyzed": len(results),
            "total_lines": total_lines,
            "warnings": warnings,
            "results": results
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@mcp.tool()
def save_python_analysis_report(dir_path: str, output_name: str = "") -> str:
    """
    Analyse un dossier Python et sauvegarde le rapport dans generated/ (Markdown + JSON).
    Paramètres :
      - dir_path : dossier à analyser
      - output_name : nom de base du fichier (par défaut : analyse_<nom_dossier>)
    """
    try:
        if not os.path.isdir(dir_path):
            return json.dumps({"status": "error", "message": f"Dossier introuvable : {dir_path}"})

        analysis_result = json.loads(analyze_python_directory(dir_path))
        if analysis_result.get("status") != "success":
            return json.dumps(analysis_result)

        os.makedirs(GENERATED_DIR, exist_ok=True)

        base_name = output_name or f"analyse_{os.path.basename(os.path.normpath(dir_path))}"
        md_path = os.path.join(GENERATED_DIR, f"{base_name}.md")
        json_path = os.path.join(GENERATED_DIR, f"{base_name}.json")

        # --- JSON ---
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)

        # --- Markdown ---
        md_lines = [
            f"# Rapport d'analyse Python\n",
            f"**Dossier analysé :** `{dir_path}`\n",
            f"**Fichiers analysés :** {analysis_result['files_analyzed']}\n",
            f"**Lignes totales :** {analysis_result['total_lines']}\n",
            f"**Date :** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            "\n---\n"
        ]

        if analysis_result.get("warnings"):
            md_lines.append("\n## ⚠️ Anomalies détectées\n")
            for warn in analysis_result["warnings"]:
                md_lines.append(f"- {warn}\n")
            md_lines.append("\n---\n")

        for file_info in analysis_result["results"]:
            md_lines.append(f"\n## Fichier : `{file_info['file']}`\n")
            md_lines.append(f"- **Lignes :** {file_info['lines']}\n")

            if file_info.get("imports"):
                md_lines.append(f"- **Imports :**\n")
                for imp in file_info["imports"]:
                    md_lines.append(f"  - `{imp}`\n")

            if file_info.get("classes"):
                md_lines.append(f"- **Classes :**\n")
                for cls in file_info["classes"]:
                    md_lines.append(f"  - **`{cls['name']}`**\n")
                    if cls.get("methods"):
                        md_lines.append(f"    - Méthodes : {', '.join(cls['methods'])}\n")

            if file_info.get("functions"):
                md_lines.append(f"- **Fonctions :**\n")
                for func in file_info["functions"]:
                    args = ", ".join(func.get("args", []))
                    md_lines.append(f"  - `{func['name']}({args})`\n")

        with open(md_path, "w", encoding="utf-8") as f:
            f.writelines(md_lines)

        return json.dumps({
            "status": "success",
            "message": "Rapport généré avec succès",
            "markdown": md_path,
            "json": json_path,
            "files_analyzed": analysis_result["files_analyzed"],
            "total_lines": analysis_result["total_lines"],
            "warnings": analysis_result.get("warnings", [])
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


if __name__ == "__main__":
    print("🚀 [Python-Analyzer] Serveur démarré.", file=sys.stderr)
    mcp.run(transport="stdio")