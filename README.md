Django Bedrock Panel

# Run the ServerDownload script to fetch and unzip latest bedrock server
1. Run ./ServerDownload.sh

# Open DockerFile and change 54222 with your port number in both places
# Run the following command to create a docker image:
2. docker build -t mc-panel .

# Open docker-compose.yml and change the port numbers 54222 and 19134,
# with your port numbers
3. docker compose up -d

# List containers
4. docker ps -a
