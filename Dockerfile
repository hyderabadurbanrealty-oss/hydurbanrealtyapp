# Dockerfile for running all three services in one Railway container
# Uses the .NET SDK base image and installs Python + Node so all runtimes are available.

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS base

# Install Python and Node.js (including npm)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-pip \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

# Set the workdir where the repository will be copied
WORKDIR /app

# Copy everything into the container
COPY . .

# Install frontend dependencies (required for ng/Angular CLI)
RUN cd frontend && npm install

# Ensure the start script is executable
RUN chmod +x ./start.sh

# Expose ports commonly used by the services
# (Adjust as needed for your app configuration)
EXPOSE 5000 4200 3000 5173

# Run the start script (keeps the container alive by waiting on subprocesses)
CMD ["bash", "./start.sh"]
