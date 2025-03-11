from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr, count, when, max as spark_max, sum as spark_sum
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType
import yaml, json, os

# Inisialisasi Spark
spark = SparkSession.builder.appName("DataQualityCheck")\
    .config("spark.jars.packages", "mysql:mysql-connector-java:8.0.33")\
    .getOrCreate()

# # Load konfigurasi YAML
# with open("metrics/chrono_metrics.yml", "r") as file:
#     config = yaml.safe_load(file)

def load_table(config, section, role):
    """ Load table based on config and role (source/target) """
    if role not in config[section]:
        print(f"No {role} configuration found for {section}")
        return None
    
    db_config = config[section][role]
    print(f"Loading {role} table: {db_config['database']}.{db_config['table']}")
    
    try:
        return (spark.read.format("jdbc")
                .option("url", f"jdbc:mysql://192.168.241.1:3306/{db_config['database']}")
                .option("dbtable", db_config['table'])
                .option("user", "testing123")
                .option("password", "testing1234")
                .option("driver", "com.mysql.cj.jdbc.Driver")
                .load())
    except Exception as e:
        print(f"Error loading {role} table for {section}: {str(e)}")
        return None

def validate(rule_name, rule, df):
    invalid_data = df.filter(~expr(rule))
    invalid_rows = invalid_data.count()
    total_rows = df.count()
    pass_rate = ((total_rows - invalid_rows) / total_rows) * 100 if total_rows > 0 else 0
    invalid_data = invalid_data.withColumn(rule_name, when(col(rule_name).isNull(), "NULL").otherwise(col(rule_name)))
    
    df_invalid_agg = (invalid_data.groupBy(rule_name).count().orderBy("count", ascending=False))
    invalid_list = df_invalid_agg.collect()
    invalid_list = json.dumps([{"value": row[rule_name], "count": row["count"]} for row in invalid_list], indent=1)

    return (rule_name, total_rows, (total_rows - invalid_rows), pass_rate, invalid_list)

def save_result(df, table_name):
    jdbc_url = f"jdbc:mysql://192.168.241.1:3306/dqu"
    properties = {
        "user": "testing123",
        "password": "testing1234",
        "driver": "com.mysql.cj.jdbc.Driver"
    }
    df.write.jdbc(url=jdbc_url, table=table_name, mode="append", properties=properties)

folder_path = "metrics" 
yml_files = [f for f in os.listdir(folder_path) if f.endswith(".yml")]
for yml in yml_files:
    with open(f"{folder_path}/{yml}", "r") as file:
        config = yaml.safe_load(file)

    for dq_section in config:
        if dq_section.startswith("dq_"):
            dq_config = config[dq_section]
            source_df = load_table(config, dq_section, "source")
            target_df = load_table(config, dq_section, "target")

            # if source_df is None:
            #     print(f"Skipping {dq_section} due to missing source table")
            #     continue

            # Validasi completeness
            if "completeness" in dq_config["measure"]:
                completeness_rules = dq_config["measure"]["completeness"]["dq_rules"]
                result = []
                for rule_name, rule in completeness_rules.items():

                    # if source_df is not None:
                    #     db = config[dq_section]['source']['database']
                    #     table = config[dq_section]['source']['table']
                    #     validate_result = validate(rule_name, rule, source_df)
                    #     result.append( (db, table) + validate_result )
                    
                    if target_df is not None:
                        db = config[dq_section]['target']['database']
                        table = config[dq_section]['target']['table']
                        validate_result = validate(rule_name, rule, target_df)
                        result.append( (db, table) + validate_result )

                schema = StructType([
                    StructField("database", StringType(), True),
                    StructField("table", StringType(), True),
                    StructField("column", StringType(), True),
                    StructField("count_data", IntegerType(), True),
                    StructField("count_valid", IntegerType(), True),
                    StructField("percentage_valid", FloatType(), True),
                    StructField("data_invalid", StringType(), True),
                ])

                df_result = spark.createDataFrame(result, schema)
                # df_result.show()
                save_result(df_result, 'df_dqu_completeness')

            # Validasi accuracy
            if "accuracy" in dq_config["measure"] and target_df is not None:
                accuracy_rules = dq_config["measure"]["accuracy"]["dq_rules"]
                groupby_cols = dq_config["measure"]["accuracy"]["source_filter"]["groupby"].split(',')

                source_grouped = source_df.groupBy(*groupby_cols)
                target_grouped = target_df.groupBy(*groupby_cols)
                df_result = source_df.select(*groupby_cols)
                for rule_name, rule in accuracy_rules.items():
                    agg_func = rule['aggfunc']
                    threshold = rule.get('threshold', 0)
                    source_col = rule['source_cols']
                    target_col = rule['target_cols']
                    
                    if agg_func == "max":
                        source_grouped_agg = source_grouped.agg(spark_max(source_col).alias(f"max_source_{source_col}"))
                        target_grouped_agg = target_grouped.agg(spark_max(target_col).alias(f"max_target_{target_col}"))
                    elif agg_func == "sum":
                        source_grouped_agg = source_grouped.agg(spark_sum(source_col).alias(f"sum_source_{source_col}"))
                        target_grouped_agg = target_grouped.agg(spark_sum(target_col).alias(f"sum_target_{target_col}"))

                    accuracy_check = source_grouped_agg.join(target_grouped_agg, groupby_cols, "inner")
                    col_prefix = "max" if agg_func == "max" else "sum"
                    accuracy_check = accuracy_check.withColumn(f"{target_col}_accuracy", (col(f"{col_prefix}_source_{source_col}") - col(f"{col_prefix}_target_{target_col}")) <= threshold)

                    df_result = df_result.join(accuracy_check, groupby_cols, "outer")
                # df_result.show()
                db_target = config[dq_section]['target']['database']
                table_target = config[dq_section]['target']['table']
                db_source = config[dq_section]['source']['database']
                table_source = config[dq_section]['source']['table']
                save_result(df_result, f"df_dqu_accuracy_{table_source}_to_{table_target}")

# Stop Spark
spark.stop()
