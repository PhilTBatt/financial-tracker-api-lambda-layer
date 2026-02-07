# Lambda Function For QIF Processing & DynamoDB Integration

This AWS Lambda function processes QIF transaction files uploaded to S3 and stores the parsed transactions in DynamoDB.  
It is to be used in conjunction with an Angular front end and a Java Spring Boot API.

Front end repo: https://github.com/PhilTBatt/financial-tracker-app
API repo: https://github.com/PhilTBatt/financial-tracker-api

## AWS Setup
Ensure AWS credentials are configured locally or via environment variables.

The Lambda requires permissions to:
- Read objects from the S3 upload bucket
- Write/read items in the DynamoDB table
- Write logs to CloudWatch

## Upload & Processing Flow

1. Upload a QIF file to the configured S3 bucket  
2. The Lambda function is triggered automatically  
3. The function:
   - Reads the file from S3
   - Parses it into a DataFrame using `process_file()`
   - Saves transactions to DynamoDB via `save_transactions_to_db()`

## Local Testing

Run python tests:
```bash
python -m pytest
```
Build the Lambda:
```bash
sam build
```
Invoke the Lambda locally with SAM:
```bash
sam local invoke -e events/event.json
```
(Requires test file in S3: financial-files-bucket/lambda-event-test-example.qif)

## Deploy
Deploy to aws: 
```bash
sam deploy --resolve-image-repos
```
