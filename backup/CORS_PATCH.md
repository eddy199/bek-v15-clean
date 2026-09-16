# Patch CORS pour le cloud

Dans ton fichier `E:\\workspacekimi\\app.py`, trouve la ligne :

    CORS(app, origins=["http://localhost:3000", "http://localhost:3001"])

Remplace-la par :

    CORS(app, origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://*.vercel.app",
        "https://*.onrender.com",
    ])

Si tu utilises `flask_cors` avec `@cross_origin()`, remplace par :

    @cross_origin(origins=["http://localhost:3000", "https://*.vercel.app", "https://*.onrender.com"])
