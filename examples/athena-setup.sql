-- Run as the dataset owner. Replace YOUR_BUCKET. Not executed by the planner.
CREATE DATABASE IF NOT EXISTS quick_query_demo;

CREATE EXTERNAL TABLE quick_query_demo.flights_raw (
  year string, month string, dayofmonth string, dayofweek string,
  deptime string, crsdeptime string, arrtime string, crsarrtime string,
  uniquecarrier string, flightnum string, tailnum string,
  actualelapsedtime string, crselapsedtime string, airtime string,
  arrdelay string, depdelay string, origin string, dest string, distance string,
  taxiin string, taxiout string, cancelled string, cancellationcode string,
  diverted string, carrierdelay string, weatherdelay string, nasdelay string,
  securitydelay string, lateaircraftdelay string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',', 'quoteChar'='"', 'escapeChar'='\\')
LOCATION 's3://YOUR_BUCKET/quick-query/input/2008/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE OR REPLACE VIEW quick_query_demo.flights AS
SELECT try_cast(month AS integer) AS Month,
       try_cast(dayofweek AS integer) AS DayOfWeek,
       try_cast(crsdeptime AS integer) AS CRSDepTime,
       uniquecarrier AS UniqueCarrier,
       try_cast(arrdelay AS bigint) AS ArrDelay,
       origin AS Origin, dest AS Dest,
       try_cast(cancelled AS integer) AS Cancelled,
       try_cast(diverted AS integer) AS Diverted
FROM quick_query_demo.flights_raw;
