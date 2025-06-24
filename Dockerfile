# Use an official Python image as the base
FROM python:3.12

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory
WORKDIR /app

# Copy the bot files to the container
COPY . .

# Install Python dependencies
RUN pip install -r requirements.txt

# Run the bot
CMD ["python", "bot.py"]