[Django Bedrock Panel]

# Run the ServerDownload.sh script to fetch and unzip latest bedrock server:
chmod u+x ServerDownload.sh && ./ServerDownload.sh

# Run the following command with YOUR PORT number to create a docker image:
docker build --build-arg PORT=50222 -t mc-panel .

# Open the .env file and replace PORT and MCPORT with your port numbers, then run:
docker compose up -d

# List containers:
docker ps -a
