from pyspark.sql import SparkSession

# Inisialisasi SparkSession
spark = SparkSession.builder \
    .appName("MySQL_Spark") \
    .config("spark.jars", "/var/spark_docker/src/jdbc/mysql-connector-java-8.0.17.jar") \
    .getOrCreate()

# Konfigurasi koneksi
jdbc_url = "jdbc:mysql://192.168.241.1:3306/datamart_actual"
# table_name = "your_table"
properties = {
    "user": "testing123",
    "password": "testing1234",
    "driver": "com.mysql.cj.jdbc.Driver"
}

# Membaca data dari MySQL ke DataFrame
df = spark.read.jdbc(url=jdbc_url, table="master_site_datamart", properties=properties)

# Menampilkan DataFrame
df.show()
