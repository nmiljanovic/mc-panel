FROM python:3-slim

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

# Create dir inside container under root 
WORKDIR /mcpanel
COPY . /mcpanel
