# Use an official Python image as the base
FROM python:3.11-slim

# Install system dependencies, including FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code into the container
COPY . .

# Expose the port Streamlit will run on (default is 8501)
EXPOSE 8501

# Run your Streamlit app
CMD ["streamlit", "run", "connect.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
