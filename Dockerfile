# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# SET ENVIRONMENT VARIABLES
ENV PLEXAPI_CONFIG_PATH='/app/.plexapi/config.ini'

# Run deleterr.py when the container launches
CMD ["python", "deleterr.py", "-v"]