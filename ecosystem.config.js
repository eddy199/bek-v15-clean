module.exports = {
  apps: [
    {
      name: "bek-api",
      script: "app.py",
      interpreter: "./venv/Scripts/pythonw.exe",
      watch: true,
      ignore_watch: ["uploads", "generated", "logs", "*.log", ".git"],
      max_memory_restart: "1G",
      error_file: "./logs/api-error.log",
      out_file: "./logs/api-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      windows_hide: true,
      env: {
        NODE_ENV: "production"
      }
    }
  ]
};