# Use Alpine Linux as base image for minimal size
FROM alpine:3.19

# Install the necessary dependencies
RUN apk update && \
    apk add --no-cache \
    python3 \
    py3-pip \
    ghostscript \
    curl \
    bash && \
    python3 -m ensurepip && \
    pip3 install --upgrade pip

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy application files
COPY main.py .

# Expose port 8000 for the API
EXPOSE 8000

# Start the API using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
