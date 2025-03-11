from pyspark.sql import SparkSession
from pyspark.sql.functions import col, regexp_extract, count, when, max as spark_max
import yaml

# Inisialisasi Spark
spark = SparkSession.builder.appName("DataQualityCheck").getOrCreate()

# Load konfigurasi YAML
with open("matrics.yml", "r") as file:
    config = yaml.safe_load(file)

dq_config = config["dq_chrono_5g"]

# Baca data dari sumber dan target
source_df = (spark.read.format("jdbc")
             .option("url", f"jdbc:mariadb://your_host/{dq_config['source']['database']}")
             .option("dbtable", dq_config['source']['table'])
             .option("user", "your_user")
             .option("password", "your_password")
             .load())

target_df = (spark.read.format("jdbc")
             .option("url", f"jdbc:mariadb://your_host/{dq_config['target']['database']}")
             .option("dbtable", dq_config['target']['table'])
             .option("user", "your_user")
             .option("password", "your_password")
             .load())

# Validasi completeness
completeness_rules = dq_config['measure']['completeness']['dq_rules']
for rule_name, rule in completeness_rules.items():
    completeness_check = source_df.withColumn("valid", when(expr(rule), 1).otherwise(0))
    completeness_rate = completeness_check.agg((count(when(col("valid") == 1, True)) / count("*")).alias("rate"))
    completeness_rate.show()

# Validasi accuracy
accuracy_rules = dq_config['measure']['accuracy']['dq_rules']
groupby_cols = dq_config['measure']['accuracy']['source_filter']['groupby'].split(',')

source_grouped = source_df.groupBy(*groupby_cols).agg(
    spark_max("longitude").alias("max_longitude"),
    spark_max("latitude").alias("max_latitude"),
    spark_max("frequency_mhz").alias("max_frequency_mhz")
)

target_grouped = target_df.groupBy(*groupby_cols).agg(
    spark_max("longitude").alias("max_longitude"),
    spark_max("latitude").alias("max_latitude"),
    spark_max("frequency_mhz").alias("max_frequency_mhz")
)

accuracy_check = source_grouped.join(target_grouped, groupby_cols, "inner")

for rule_name, rule in accuracy_rules.items():
    threshold = rule['threshold']
    source_col = rule['source_cols']
    target_col = rule['target_cols']
    accuracy_check = accuracy_check.withColumn(f"{rule_name}_check", (col(f"max_{source_col}") - col(f"max_{target_col}")) <= threshold)

accuracy_check.show()

# Stop Spark
spark.stop()
