FROM public.ecr.aws/lambda/python:3.13

# Copy requirements.txt and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy your function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set the Lambda handler
CMD ["lambda_function.lambda_handler"]