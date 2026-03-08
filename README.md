Django Bedrock Panel

# Run the ServerDownload script to fetch and unzip latest bedrock server
1. Run ./ServerDownload.sh

# Run the following command with your PORT number to create a docker image:
2. docker build --build-arg PORT=50222 -t mc-panel .

# Open the .env file and replace PORT and MCPORT with your port numbers
3. docker compose up -d

# List containers
4. docker ps -a
