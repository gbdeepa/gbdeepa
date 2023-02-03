import sys
import boto3
import json
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from py4j.java_gateway import java_import
from pyspark.sql.types import StructType, StructField, StringType, IntegerType
SNOWFLAKE_SOURCE_NAME = "net.snowflake.spark.snowflake"
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
java_import(spark._jvm, SNOWFLAKE_SOURCE_NAME)
spark._jvm.net.snowflake.spark.snowflake.SnowflakeConnectorUtils.enablePushdownSession(spark._jvm.org.apache.spark.sql.SparkSession.builder().getOrCreate())
import yaml

# Getting DB credentials from Secrets Manager
client = boto3.client("secretsmanager", region_name="us-east-1")

get_secret_value_response = client.get_secret_value(
       SecretId="snowflake_credentials"
)

secret = get_secret_value_response['SecretString']
secret = json.loads(secret)

sf_username = secret.get('SNOWFLAKE_USER')
sf_password = secret.get('SNOWFLAKE_PWD')

with open("config.yaml", "r") as stream:
  try:
      c=yaml.safe_load(stream)
  except yaml.YAMLError as exc:
      print(exc)


sfOptions = {
"sfURL" : c['glue_to_snowflake']['url'],
"sfRole" : c['glue_to_snowflake']['role'],
"sfUser" : sf_username,
"sfPassword" : sf_password,
"sfDatabase" : c['glue_to_snowflake']['db'],
"sfSchema" : c['glue_to_snowflake']['schema'],
"sfWarehouse" : c['glue_to_snowflake']['warehouse'],
}


# Employee data base schema
schema = StructType(
      [
          StructField("Employee_id", IntegerType(), nullable=True),
          StructField("First_name", StringType(), nullable=True),
          StructField("Last_name", StringType(), nullable=True),
          StructField("Email", StringType(), nullable=True),
          StructField("Salary", IntegerType(), nullable=True),
          StructField("Department", StringType(), nullable=True)
      ]
  )

# Read from s3 location into a Spark Dataframe
input_bucket = c['glue_to_snowflake']['input_s3_bucket']
s3_uri = f"s3://{input_bucket}/data/employee.csv"

# Read from S3 and load into a Spark Dataframe
df = spark.read.option("header", True).csv(path=s3_uri,sep=',',schema=schema)

# Perform any kind of transformations on your data
df1 = df.filter( (df.Department  == "IT") | (df.Department  == "Mkt") )

# Write the Data Frame contents back to Snowflake in a new table - stage_employee
df1.write.format(SNOWFLAKE_SOURCE_NAME).options(**sfOptions).option("dbtable", "stage_employee").mode("overwrite").save()

job.commit()
