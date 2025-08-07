FROM public.ecr.aws/lambda/python:3.13

# Copy requirements.txt and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy your function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Copy the RIE binary and entrypoint script into the container
ADD aws-lambda-rie /usr/local/bin/aws-lambda-rie
COPY entry_script.sh /entry_script.sh

# Make the entry script executable
RUN chmod +x /entry_script.sh

ENV _HANDLER=lambda_function.lambda_handler

# Use the script as the container entrypoint
ENTRYPOINT [ "/entry_script.sh" ]