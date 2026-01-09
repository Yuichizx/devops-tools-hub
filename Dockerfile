FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    SONAR_SCANNER_VERSION=7.1.0.4889 \
    SONAR_SCANNER_HOME=/opt/sonar-scanner \
    HOME=/root \
    PATH="/opt/sonar-scanner/bin:${PATH}"

# Create writable cache directory
RUN mkdir -p /cache

# Set working directory inside the container
WORKDIR /app

# 1. Install System Dependencies & Runtime (Java, Node, Git, etc.) in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    unzip \
    git \
    build-essential \
    net-tools \
    default-jre \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Install SonarQube Scanner
RUN wget -qO /tmp/sonar-scanner.zip \
      "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VERSION}-linux-x64.zip" \
    && unzip -q /tmp/sonar-scanner.zip -d /opt/ \
    && mv /opt/sonar-scanner-${SONAR_SCANNER_VERSION}-linux-x64 ${SONAR_SCANNER_HOME} \
    && rm /tmp/sonar-scanner.zip

# 3. Copy requirements and install Python dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# 4. Playwright Setup: Install Chromium and its system dependencies
RUN playwright install chromium && \
    playwright install-deps chromium && \
    rm -rf /var/lib/apt/lists/*

# 5. Copy application code to /app
COPY . .

# Expose port used by Flask/Waitress
EXPOSE 5000

# Run the application
CMD ["python3", "run.py"]