# Include python dep
FROM python:3-slim

# Internal usage between containers: not port forwarding
ARG PORT
EXPOSE $PORT

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
    wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create directory inside container under root 
WORKDIR /mcpanel
COPY . /mcpanel

# JSON form that explicitly calls a shell to expand PORT 
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} manager.wsgi"]
