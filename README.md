# DevOps Tools Hub

An **All-in-One** web application for DevOps teams and Developers, providing various utility tools, a code security scanner (SonarQube), and configuration generators in a single, modern, centralized interface.

## 🚀 Key Features

### 🛡️ Security & Code Quality
*   **Repo Scanner**: Graphical interface to run SonarQube Scanner on Git repositories. Supports parameter customization (*exclusions, inclusions, branch*).
*   **GitHub Access Checker**: Verify user roles/permissions on specific GitHub organizations or repositories.
*   **Password & Hash Generator**: Instantly generate strong passwords and hashes (MD5, SHA256, Bcrypt).

### 🛠️ Developer Utilities
*   **Diff Checker**: Compare two text/code blocks to see line-by-line and character-level differences.
*   **Formatters**: JSON Beautifier, SQL Formatter.
*   **Converters**: Base64 Encoder/Decoder, Time Converter (Unix/Epoch), YAML to JSON, JSON to Go Struct.
*   **Calculators**: IP Calculator (Subnetting), Chmod Calculator (Unix Permissions).

### ⚙️ Automation Generators
*   **Crontab Generator**: Visual UI to create cron schedule expressions.
*   **Dockerfile Generator**: Basic templates for various programming languages.

## 📋 Prerequisites

Before starting, ensure you have:
*   **Python 3.10+** (for manual deployment)
*   **Docker & Docker Compose** (optional, for containerized deployment)
*   Access to a **SonarQube** server (if you intend to use the Repo Scanner feature)

## 📦 Installation & Usage

### Option 1: Using Docker (Recommended)

1.  **Clone Repository**
    ```bash
    git clone https://github.com/username/devops-tools-hub.git
    cd devops-tools-hub
    ```

2.  **Configure Environment**
    Copy the example file `.env-example` to `.env`:
    ```bash
    cp .env-example .env
    ```
    Edit the `.env` file and adjust the values (see configuration guide below).

3.  **Build & Run**
    ```bash
    docker build -t devops-tools-hub .
        docker run -d -p 5000:5000 --env-file .env --name devops-hub devops-tools-hub
        ```
        Access the application at `http://localhost:5000`.
    
    ### Option 2: Manual Installation (Local)
    
    1.  **Setup Virtual Environment**
        ```bash
        python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run Application**
    Ensure `.env` is configured.
    ```bash
    python run.py
    ```

## 🔧 Configuration (.env)

The application is highly flexible and configured via *Environment Variables*.

| Variable | Required? | Description | Default |
| :--- | :---: | :--- | :--- |
| `FLASK_SECRET_KEY` | **YES** | Secret key for sessions & security. | - |
| `SONAR_HOST_URL` | No | SonarQube Server URL (for scanner). | - |
| `SONAR_LOGIN_TOKEN`| No | SonarQube Authentication Token. | - |
| `APP_TITLE` | No | App title in header/browser tab. | DevOps Tools Hub |
| `APP_LOGO` | No | App logo URL/Path. | `/static/images/logo.png` |
| `GITHUB_ACCESS_PASSWORD` | No | Password for accessing critical GitHub tools. | - |
| `GITHUB_TOKEN` | No | GitHub Personal Access Token (Alternative to .netrc). | - |

## Installation & Setup

You can change the application's look and feel to match your company branding without touching the code.

### 1. Changing Name & Description
Simply modify the following variables in your `.env` file:
```env
APP_TITLE="My Company Tools"
APP_DESCRIPTION="Internal Tools for Engineering Team"
```

### 2. Changing Logo
There are two ways to change the logo:

**Method A: Replace File (Easiest)**
Overwrite the existing images in the `static/images/` folder:
*   `static/images/logo.png`: Main logo (recommended height: 40-60px).
*   `static/images/favicon.png`: Browser tab icon.

**Method B: Custom URL/Path**
Host your logo anywhere or place it in static, then update `.env`:
```env
APP_LOGO="https://your-company.com/logo.png"
# Or a local path
APP_LOGO="/static/custom-logo.svg"
```

## 🤝 Contributing

Contributions are welcome! Please create a *Pull Request* for new features, bug fixes, or documentation improvements.

## 📄 License

This project is distributed under the MIT License. See `LICENSE` for more details.
