import yaml
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from datetime import datetime, timedelta

# Inisialisasi Spark
spark = SparkSession.builder.appName("DataQualityCheck").getOrCreate()

# Load YAML file
with open("metrics/metrics.yml", "r") as file:
    dq_config = yaml.safe_load(file)

# Ambil konfigurasi untuk amesty_master_site
dq_rules = dq_config["dq_amesty_master_site"]

# Simulasi DataFrame (Gantilah ini dengan data asli dari database)
data = [
    ("ABC123", "Site A", 100.5, -5.2, "REGIONAL 1", "NSA 1", "RTPO 1", "Some Address", "PERMANENT", "PERMANENT", "2024-03-09"),
    ("XYZ456", None, 150.0, -20.0, "REGIONAL 2", "NSA 2", "RTPO 2", None, "STO", "STO", "2024-03-08"),  # Data Invalid
]
columns = ["site_id", "site_name", "longitude", "latitude", "regional", "nsa_name", "rtpo_name", "address", "sitetype_name", "sitetype_code", "last_sync"]
df = spark.createDataFrame(data, columns)

# Validasi "Timeliness" (Cek apakah data sesuai tanggal yang diharapkan)
date_column = dq_rules["measure"]["timeliness"]["date_column"]
date_format = dq_rules["measure"]["timeliness"]["date_format"]
expected_delivery_days = int(dq_rules["measure"]["timeliness"]["expected_delivery"].split(":")[-1])
expected_date = (datetime.today() + timedelta(days=expected_delivery_days)).strftime("%Y-%m-%d")

timeliness_check = df.filter(col(date_column) == expected_date).count() / df.count() * 100
print(f"Timeliness Check: {timeliness_check:.2f}% data sesuai dengan tanggal yang diharapkan")

# Validasi "Completeness" berdasarkan aturan dalam dq_rules
dq_checks = dq_rules["measure"]["completeness"]["dq_rules"]

for column, condition in dq_checks.items():
    df_filter = df.filter(f"NOT ({condition})")
    failed_rows = df_filter.count()
    total_rows = df.count()
    pass_rate = ((total_rows - failed_rows) / total_rows) * 100 if total_rows > 0 else 0
    print(f"Check {column}: {pass_rate:.2f}% valid data")
    failed_value = df_filter.select(column).distinct().rdd.map(lambda row: row[0]).collect()
    if failed_value:
        print(failed_value)
        failed = "|".join("NULL" if x is None else str(x) for x in failed_value)
        print(column, failed)

# Stop Spark session
spark.stop()
