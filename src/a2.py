from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr, count, when, max as spark_max, sum as spark_sum
import yaml

# Inisialisasi Spark
spark = SparkSession.builder.appName("DataQualityCheck")\
    .config("spark.jars.packages", "mysql:mysql-connector-java:8.0.33")\
    .getOrCreate()

# Load konfigurasi YAML
with open("metrics/chrono_metrics.yml", "r") as file:
    config = yaml.safe_load(file)

def load_table(config, section, role):
    """ Load table based on config and role (source/target) """
    db_config = config[section][role]
    return (spark.read.format("jdbc")
            .option("url", f"jdbc:mysql://192.168.241.1/{db_config['database']}")
            .option("dbtable", db_config['table'])
            .option("user", "testing123")
            .option("password", "testing1234")
            .option("driver", "com.mysql.cj.jdbc.Driver")
            .load())
# "driver": "com.mysql.cj.jdbc.Driver"
for dq_section in config:
    if dq_section.startswith("dq_"):
        dq_config = config[dq_section]
        source_df = load_table(config, dq_section, "source") if "source" in dq_config else None
        target_df = load_table(config, dq_section, "target") if "target" in dq_config else None
        
        # Validasi completeness
        if "completeness" in dq_config["measure"]:
            completeness_rules = dq_config["measure"]["completeness"]["dq_rules"]
            for rule_name, rule in completeness_rules.items():
                completeness_check = source_df.withColumn("valid", when(expr(rule), 1).otherwise(0))
                completeness_rate = completeness_check.agg((count(when(col("valid") == 1, True)) / count("*")).alias("rate"))
                completeness_rate.show()
        
#         # Validasi accuracy
#         if "accuracy" in dq_config["measure"] and source_df and target_df:
#             accuracy_rules = dq_config["measure"]["accuracy"]["dq_rules"]
#             groupby_cols = dq_config["measure"]["accuracy"]["source_filter"]["groupby"].split(',')

#             source_grouped = source_df.groupBy(*groupby_cols)
#             target_grouped = target_df.groupBy(*groupby_cols)

#             for rule_name, rule in accuracy_rules.items():
#                 agg_func = rule['aggfunc']
#                 threshold = rule.get('threshold', 0)
#                 source_col = rule['source_cols']
#                 target_col = rule['target_cols']
                
#                 if agg_func == "max":
#                     source_grouped = source_grouped.agg(spark_max(source_col).alias(f"max_{source_col}"))
#                     target_grouped = target_grouped.agg(spark_max(target_col).alias(f"max_{target_col}"))
#                 elif agg_func == "sum":
#                     source_grouped = source_grouped.agg(spark_sum(source_col).alias(f"sum_{source_col}"))
#                     target_grouped = target_grouped.agg(spark_sum(target_col).alias(f"sum_{target_col}"))
                
#             accuracy_check = source_grouped.join(target_grouped, groupby_cols, "inner")

#             for rule_name, rule in accuracy_rules.items():
#                 threshold = rule.get('threshold', 0)
#                 source_col = rule['source_cols']
#                 target_col = rule['target_cols']
#                 agg_func = rule['aggfunc']
#                 col_prefix = "max" if agg_func == "max" else "sum"
#                 accuracy_check = accuracy_check.withColumn(f"{rule_name}_check", (col(f"{col_prefix}_{source_col}") - col(f"{col_prefix}_{target_col}")) <= threshold)

#             accuracy_check.show()

# # Stop Spark
# spark.stop()
