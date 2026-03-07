FROM python:3-slim

# Container listen port: does not publish
EXPOSE 54222

# Keep Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turn off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY requirements.txt .
RUN python -m pip install -r requirements.txt
# ... other dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libcurl4 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
# ... rest of the Dockerfile

WORKDIR /mc_panel
COPY . /mc_panel

# Create non-root user with explicit UID and add permission to access /app
RUN adduser -u 5678 --disabled-password --gecos "" $USER && chown -R $USER /app
USER appuser

CMD ["gunicorn", "--bind", "0.0.0.0:54222", "manager.wsgi"]
