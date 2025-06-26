FROM python:3.12

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libsodium23 \
    pulseaudio \
    alsa-utils \
    libasound2-dev
# Set the working directory
WORKDIR /app

# Copy the bot files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Run the bot
CMD ["python", "bot.py"]
