from pyspark.sql import SparkSession
from pyspark.sql.functions import col

# 1️⃣ Create a Spark Session
spark = SparkSession.builder \
    .appName("SparkQuickTest") \
    .config("spark.driver.memory", "2g") \
    .getOrCreate()

# 2️⃣ Create Example Data
data = [
    (1, "Alice", 25),
    (2, "Bob", 30),
    (3, "Charlie", 35)
]

columns = ["ID", "Name", "Age"]

# 3️⃣ Create a DataFrame
df = spark.createDataFrame(data, columns)

# 4️⃣ Show Data
print("✅ Spark DataFrame:")
df.show()

# 5️⃣ Perform Basic Operations
print("✅ Filter Data (Age > 28):")
df.filter(col("Age") > 28).show()

print("✅ Select and Sort:")
df.select("Name", "Age").orderBy(col("Age").desc()).show()

# 6️⃣ Stop Spark Session
spark.stop()
