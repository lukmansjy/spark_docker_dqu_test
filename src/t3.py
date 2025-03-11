import yaml
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr, count, when
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType
from datetime import datetime, timedelta
import json

# Inisialisasi Spark Session dengan Auto-Download MySQL JDBC Driver
spark = SparkSession.builder \
    .appName("DataQualityCheck") \
    .config("spark.jars.packages", "mysql:mysql-connector-java:8.0.33") \
    .getOrCreate()

# Load aturan validasi dari YAML
with open("metrics/site.yml", "r") as file:
    dq_config = yaml.safe_load(file)

# for key in dq_config.keys():
#   print(key)

dq_rules = dq_config["dq_master_site"]

# Konfigurasi koneksi ke MySQL
MYSQL_HOST = "192.168.241.1"
MYSQL_PORT = "3306"
MYSQL_USER = "testing123"
MYSQL_PASSWORD = "testing1234"
MYSQL_DATABASE = dq_rules["target"]["database"]
MYSQL_TABLE = dq_rules["target"]["table"]

# Baca data dari MySQL ke dalam DataFrame PySpark
jdbc_url = f"jdbc:mysql://{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
properties = {
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "driver": "com.mysql.cj.jdbc.Driver"
}

df = spark.read.jdbc(url=jdbc_url, table=MYSQL_TABLE, properties=properties)

# Timeliness Check: Periksa apakah tanggal sesuai dengan expected_delivery
date_column = dq_rules["measure"]["timeliness"]["date_column"]
expected_delivery_days = int(dq_rules["measure"]["timeliness"]["expected_delivery"].split(":")[-1])
expected_date = (datetime.today() + timedelta(days=expected_delivery_days)).strftime("%Y-%m-%d")

timeliness_check = df.filter(col(date_column) == expected_date).count() / df.count() * 100
print(f"Timeliness Check: {timeliness_check:.2f}% data sesuai dengan tanggal yang diharapkan")

# Completeness Check berdasarkan aturan YAML
dq_checks = dq_rules["measure"]["completeness"]["dq_rules"]
print(dq_checks)




result = []
for column, condition in dq_checks.items():
    # df_filter = df.filter(f"NOT ({condition})")
    df_filter = df.filter(expr(f"NOT ({condition})"))
    # df2.show()
    print(condition)
    df_x = df_filter.select(column)
    df_x.show()
    failed_rows = df_filter.count()
    total_rows = df.count()
    pass_rate = ((total_rows - failed_rows) / total_rows) * 100 if total_rows > 0 else 0
    # print(f"Check {column}: {pass_rate:.2f}% valid data")
    # failed_value = df_filter.select(column).distinct().rdd.map(lambda row: row[0]).collect()
    # failed = ""
    # if failed_value:
    #     failed = "|".join("NULL Value" if x is None else str(x) for x in failed_value)
    #     # print(column, failed)

    df_filter = df_filter.withColumn(column, when(col(column).isNull(), "NULL").otherwise(col(column)))
    df_result = (
      # df.groupBy(column)
      # .agg(count("*").alias("total"))
      # .orderBy(col("total").desc())
      df_filter.groupBy(column).count().orderBy("count", ascending=False)
    )

    # df_result.show()

    list_failed = df_result.collect()  # Ambil hasil sebagai list
    failed = json.dumps([{"value": row[column], "count": row["count"]} for row in list_failed], indent=2)
    
    result.append((MYSQL_DATABASE, MYSQL_TABLE, column, total_rows, (total_rows - failed_rows), pass_rate, failed))

# print(result)

# Define Schema
schema = StructType([
    StructField("database", StringType(), True),
    StructField("table", StringType(), True),
    StructField("column", StringType(), True),
    StructField("count_data", IntegerType(), True),
    StructField("count_valid", IntegerType(), True),
    StructField("percentage_valid", FloatType(), True),
    StructField("data_invalid", StringType(), True),
])
# Create Empty DataFrame
df_result = spark.createDataFrame(result, schema)
df_result.show()

jdbc_url = f"jdbc:mysql://{MYSQL_HOST}:{MYSQL_PORT}/dqu"
df_result.write.jdbc(url=jdbc_url, table="test_result", mode="append", properties=properties)
# Stop Spark session
spark.stop()
