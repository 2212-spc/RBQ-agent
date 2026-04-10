create table Student (
        StuID        INTEGER PRIMARY KEY,
        LName        VARCHAR(12),
        Fname        VARCHAR(12),
        Age      INTEGER,
        Sex      VARCHAR(1),
        Major        INTEGER,
        Advisor      INTEGER,
        city_code    VARCHAR(3),
        FOREIGN KEY(city_code) REFERENCES City(city_code)
 );

create table Direct_distance (
  city1_code varchar(3) ,
  city2_code varchar(3) ,
  distance INTEGER,
  FOREIGN KEY(city1_code) REFERENCES City(city_code),
  FOREIGN KEY(city2_code) REFERENCES City(city_code)
  
) ;


create table City (
       city_code  	VARCHAR(3) PRIMARY KEY,
       city_name  	VARCHAR(25),
       state		VARCHAR(2),
       country		VARCHAR(25),
       latitude		FLOAT,
       longitude	FLOAT
);


insert into Student values ( 1001, 'Smith', 'Linda', 18, 'F', 600, 1121,'BAL');
 insert into Student values ( 1002, 'Kim', 'Tracy', 19, 'F', 600, 7712,'HKG');
 insert into Student values ( 1003, 'Jones', 'Shiela', 21, 'F', 600, 7792,'WAS');
 insert into Student values ( 1004, 'Kumar', 'Dinesh', 20, 'M', 600, 8423,'CHI');
 insert into Student values ( 1005, 'Gompers', 'Paul', 26, 'M', 600, 1121,'YYZ');
 insert into Student values ( 1006, 'Schultz', 'Andy', 18, 'M', 600, 1148,'BAL');
 insert into Student values ( 1007, 'Apap', 'Lisa', 18, 'F', 600, 8918,'PIT');
 insert into Student values ( 1008, 'Nelson', 'Jandy', 20, 'F', 600, 9172,'BAL');
 insert into Student values ( 1009, 'Tai', 'Eric', 19, 'M', 600, 2192,'YYZ');
 insert into Student values ( 1010, 'Lee', 'Derek', 17, 'M', 600, 2192,'HOU');
 insert into Student values ( 1011, 'Adams', 'David', 22, 'M', 600, 1148,'PHL');
 insert into Student values ( 1012, 'Davis', 'Steven', 20, 'M', 600, 7723,'PIT');
 insert into Student values ( 1014, 'Norris', 'Charles', 18, 'M', 600, 8741, 'DAL');
 insert into Student values ( 1015, 'Lee', 'Susan', 16, 'F', 600, 8721,'HKG');
 insert into Student values ( 1016, 'Schwartz', 'Mark', 17, 'M', 600, 2192,'DET');
 insert into Student values ( 1017, 'Wilson', 'Bruce', 27, 'M', 600, 1148,'LON');
 insert into Student values ( 1018, 'Leighton', 'Michael', 20, 'M', 600, 1121, 'PIT');
 insert into Student values ( 1019, 'Pang', 'Arthur', 18, 'M', 600, 2192,'WAS');
 insert into Student values ( 1020, 'Thornton', 'Ian', 22, 'M', 520, 7271,'NYC');
 insert into Student values ( 1021, 'Andreou', 'George', 19, 'M', 520, 8722, 'NYC');
 insert into Student values ( 1022, 'Woods', 'Michael', 17, 'M', 540, 8722,'PHL');
 insert into Student values ( 1023, 'Shieber', 'David', 20, 'M', 520, 8722,'NYC');
 insert into Student values ( 1024, 'Prater', 'Stacy', 18, 'F', 540, 7271,'BAL');
 insert into Student values ( 1025, 'Goldman', 'Mark', 18, 'M', 520, 7134,'PIT');
 insert into Student values ( 1026, 'Pang', 'Eric', 19, 'M', 520, 7134,'HKG');
 insert into Student values ( 1027, 'Brody', 'Paul', 18, 'M', 520, 8723,'LOS');
 insert into Student values ( 1028, 'Rugh', 'Eric', 20, 'M', 550, 2311,'ROC');
 insert into Student values ( 1029, 'Han', 'Jun', 17, 'M', 100, 2311,'PEK');
 insert into Student values ( 1030, 'Cheng', 'Lisa', 21, 'F', 550, 2311,'SFO');
 insert into Student values ( 1031, 'Smith', 'Sarah', 20, 'F', 550, 8772,'PHL');
 insert into Student values ( 1032, 'Brown', 'Eric', 20, 'M', 550, 8772,'ATL');
 insert into Student values ( 1033, 'Simms', 'William', 18, 'M', 550, 8772,'NAR');
 insert into Student values ( 1034, 'Epp', 'Eric', 18, 'M', 050, 5718,'BOS');
 insert into Student values ( 1035, 'Schmidt', 'Sarah', 26, 'F', 050, 5718,'WAS');

insert into Direct_distance values ( 'BAL' , 'ATL' , 576 ) ;
insert into Direct_distance values ( 'BAL' , 'BAL' , 0 ) ;
insert into Direct_distance values ( 'BAL' , 'BKK' , 9631 ) ;
insert into Direct_distance values ( 'BAL' , 'BOS' , 370 ) ;
insert into Direct_distance values ( 'BAL' , 'CHI' , 621 ) ;
insert into Direct_distance values ( 'BAL' , 'CPK' , 21 ) ;
insert into Direct_distance values ( 'BAL' , 'DAL' , 1217 ) ;
insert into Direct_distance values ( 'BAL' , 'DEL' , 7469 ) ;
insert into Direct_distance values ( 'BAL' , 'DET' , 408 ) ;
insert into Direct_distance values ( 'BAL' , 'EWR' , 169 ) ;
insert into Direct_distance values ( 'BAL' , 'FRE' , 35 ) ;
insert into Direct_distance values ( 'BAL' , 'HKG' , 8409 ) ;
insert into Direct_distance values ( 'BAL' , 'HON' , 4832 ) ;
insert into Direct_distance values ( 'BAL' , 'HOU' , 1240 ) ;
insert into Direct_distance values ( 'BAL' , 'JNB' , 7850 ) ;
insert into Direct_distance values ( 'BAL' , 'LON' , 3652 ) ;
insert into Direct_distance values ( 'BAL' , 'LOS' , 2329 ) ;
insert into Direct_distance values ( 'BAL' , 'MIA' , 946 ) ;
insert into Direct_distance values ( 'BAL' , 'NAR' , 71 ) ;
insert into Direct_distance values ( 'BAL' , 'NYC' , 185 ) ;
insert into Direct_distance values ( 'BAL' , 'PAR' , 3800 ) ;
insert into Direct_distance values ( 'BAL' , 'PEK' , 8041 ) ;
insert into Direct_distance values ( 'BAL' , 'PHL' , 105 ) ;
insert into Direct_distance values ( 'BAL' , 'PIT' , 210 ) ;
insert into Direct_distance values ( 'BAL' , 'PVD' , 328 ) ;
insert into Direct_distance values ( 'BAL' , 'ROC' , 277 ) ;
insert into Direct_distance values ( 'BAL' , 'SAN' , 2295 ) ;
insert into Direct_distance values ( 'BAL' , 'SFO' , 2457 ) ;
insert into Direct_distance values ( 'BAL' , 'TYO' , 6740 ) ;
insert into Direct_distance values ( 'BAL' , 'WAS' , 35 ) ;
insert into Direct_distance values ( 'BAL' , 'YYZ' , 347 ) ;
insert into Direct_distance values ( 'ATL' , 'BAL' , 576 ) ;
insert into Direct_distance values ( 'ATL' , 'PHL' , 665 ) ;
insert into Direct_distance values ( 'BKK' , 'BAL' , 9631 ) ;
insert into Direct_distance values ( 'BOS' , 'BAL' , 370 ) ;
insert into Direct_distance values ( 'BOS' , 'EWR' , 200 ) ;
insert into Direct_distance values ( 'BOS' , 'PAR' , 3448 ) ;
insert into Direct_distance values ( 'BOS' , 'PHL' , 280 ) ;
insert into Direct_distance values ( 'CHI' , 'BAL' , 621 ) ;
insert into Direct_distance values ( 'CHI' , 'PHL' , 678 ) ;
insert into Direct_distance values ( 'CPK' , 'BAL' , 21 ) ;
insert into Direct_distance values ( 'DAL' , 'BAL' , 1217 ) ;
insert into Direct_distance values ( 'DEL' , 'BAL' , 7469 ) ;
insert into Direct_distance values ( 'DET' , 'BAL' , 408 ) ;
insert into Direct_distance values ( 'DET' , 'EWR' , 488 ) ;
insert into Direct_distance values ( 'DET' , 'PHL' , 453 ) ;
insert into Direct_distance values ( 'EWR' , 'BAL' , 169 ) ;
insert into Direct_distance values ( 'EWR' , 'BOS' , 200 ) ;
insert into Direct_distance values ( 'EWR' , 'DET' , 488 ) ;
insert into Direct_distance values ( 'EWR' , 'LON' , 3458 ) ;
insert into Direct_distance values ( 'EWR' , 'LOS' , 2454 ) ;
insert into Direct_distance values ( 'EWR' , 'LOS' , 2454 ) ;
insert into Direct_distance values ( 'EWR' , 'PHL' , 89 ) ;
insert into Direct_distance values ( 'EWR' , 'SAN' , 2425 ) ;
insert into Direct_distance values ( 'EWR' , 'WAS' , 199 ) ;
insert into Direct_distance values ( 'FRE' , 'BAL' , 35 ) ;
insert into Direct_distance values ( 'HKG' , 'BAL' , 8409 ) ;
insert into Direct_distance values ( 'HON' , 'BAL' , 4832 ) ;
insert into Direct_distance values ( 'HOU' , 'BAL' , 1240 ) ;
insert into Direct_distance values ( 'HOU' , 'LOS' , 1385 ) ;
insert into Direct_distance values ( 'HOU' , 'PHL' , 1324 ) ;
insert into Direct_distance values ( 'HOU' , 'SAN' , 1270 ) ;
insert into Direct_distance values ( 'HOU' , 'SFO' , 1635 ) ;
insert into Direct_distance values ( 'JNB' , 'BAL' , 7850 ) ;
insert into Direct_distance values ( 'LON' , 'BAL' , 3652 ) ;
insert into Direct_distance values ( 'LON' , 'EWR' , 3458 ) ;
insert into Direct_distance values ( 'LON' , 'NYC' , 3452 ) ;
insert into Direct_distance values ( 'LON' , 'PHL' , 3546 ) ;
insert into Direct_distance values ( 'LON' , 'TYO' , 5975 ) ;
insert into Direct_distance values ( 'LON' , 'WAS' , 3650 ) ;
insert into Direct_distance values ( 'LOS' , 'BAL' , 2329 ) ;
insert into Direct_distance values ( 'LOS' , 'EWR' , 2454 ) ;
insert into Direct_distance values ( 'LOS' , 'EWR' , 2454 ) ;
insert into Direct_distance values ( 'LOS' , 'HOU' , 1385 ) ;
insert into Direct_distance values ( 'LOS' , 'PHL' , 2401 ) ;
insert into Direct_distance values ( 'LOS' , 'SAN' , 109 ) ;
insert into Direct_distance values ( 'MIA' , 'BAL' , 946 ) ;
insert into Direct_distance values ( 'NAR' , 'BAL' , 71 ) ;
insert into Direct_distance values ( 'NYC' , 'BAL' , 185 ) ;
insert into Direct_distance values ( 'NYC' , 'LON' , 3452 ) ;
insert into Direct_distance values ( 'PAR' , 'BAL' , 3800 ) ;
insert into Direct_distance values ( 'PAR' , 'BOS' , 3448 ) ;
insert into Direct_distance values ( 'PEK' , 'BAL' , 8041 ) ;
insert into Direct_distance values ( 'PHL' , 'ATL' , 665 ) ;
insert into Direct_distance values ( 'PHL' , 'BAL' , 105 ) ;
insert into Direct_distance values ( 'PHL' , 'BOS' , 280 ) ;
insert into Direct_distance values ( 'PHL' , 'CHI' , 678 ) ;
insert into Direct_distance values ( 'PHL' , 'DET' , 453 ) ;
insert into Direct_distance values ( 'PHL' , 'EWR' , 89 ) ;
insert into Direct_distance values ( 'PHL' , 'HOU' , 1324 ) ;
insert into Direct_distance values ( 'PHL' , 'LON' , 3546 ) ;
insert into Direct_distance values ( 'PHL' , 'LOS' , 2401 ) ;
insert into Direct_distance values ( 'PHL' , 'PIT' , 267 ) ;
insert into Direct_distance values ( 'PHL' , 'SAN' , 2369 ) ;
insert into Direct_distance values ( 'PHL' , 'SFO' , 2521 ) ;
insert into Direct_distance values ( 'PHL' , 'WAS' , 119 ) ;
insert into Direct_distance values ( 'PIT' , 'BAL' , 210 ) ;
insert into Direct_distance values ( 'PIT' , 'PHL' , 267 ) ;
insert into Direct_distance values ( 'PIT' , 'SAN' , 2106 ) ;
insert into Direct_distance values ( 'PVD' , 'BAL' , 328 ) ;
insert into Direct_distance values ( 'ROC' , 'BAL' , 277 ) ;
insert into Direct_distance values ( 'ROC' , 'WAS' , 296 ) ;
insert into Direct_distance values ( 'SAN' , 'BAL' , 2295 ) ;
insert into Direct_distance values ( 'SAN' , 'EWR' , 2425 ) ;
insert into Direct_distance values ( 'SAN' , 'HOU' , 1270 ) ;
insert into Direct_distance values ( 'SAN' , 'LOS' , 109 ) ;
insert into Direct_distance values ( 'SAN' , 'PHL' , 2369 ) ;
insert into Direct_distance values ( 'SAN' , 'PIT' , 2106 ) ;
insert into Direct_distance values ( 'SFO' , 'BAL' , 2457 ) ;
insert into Direct_distance values ( 'SFO' , 'HOU' , 1635 ) ;
insert into Direct_distance values ( 'SFO' , 'PHL' , 2521 ) ;
insert into Direct_distance values ( 'TYO' , 'BAL' , 6740 ) ;
insert into Direct_distance values ( 'TYO' , 'LON' , 5975 ) ;
insert into Direct_distance values ( 'WAS' , 'BAL' , 35 ) ;
insert into Direct_distance values ( 'WAS' , 'EWR' , 199 ) ;
insert into Direct_distance values ( 'WAS' , 'LON' , 3650 ) ;
insert into Direct_distance values ( 'WAS' , 'PHL' , 119 ) ;
insert into Direct_distance values ( 'WAS' , 'ROC' , 296 ) ;
insert into Direct_distance values ( 'YYZ' , 'BAL' , 347 ) ;

insert into City values ( 'BAL' , 'Baltimore' , 'MD' , 'USA' , 39.288 , -76.617 ) ;
insert into City values ( 'PIT' , 'Pittsburgh' , 'PA' , 'USA' , 40.437 , -80.000 ) ;
insert into City values ( 'PHL' , 'Philadelphia' , 'PA' , 'USA' , 39.950 , -75.150 ) ;
insert into City values ( 'WAS' , 'Washington' , 'DC' , 'USA' , 38.892 , -77.017 ) ;
insert into City values ( 'NYC' , 'New York' , 'NY' , 'USA' , 40.849 , -73.867) ;
insert into City values ( 'ATL' , 'Atlanta' , 'GA' , 'USA' , 33.763 , -84.317 ) ;
insert into City values ( 'EWR' , 'Newark' , 'NJ' , 'USA' , 40.737 , -74.167 );
insert into City values ( 'FRE' , 'Frederick' , 'MD' , 'USA' , 39.415 , -77.417 ) ;
insert into City values ( 'NAR' , 'Newark' , 'DE' , 'USA' , 39.683 , -75.750 );
insert into City values ( 'SAN' , 'San Diego' , 'CA' , 'USA' , 32.713 , -117.150) ;
insert into City values ( 'LOS' , 'Los Angeles' , 'CA' , 'USA' , 34.058 ,-118.250) ;
insert into City values ( 'HON' , 'Honolulu' , 'HI' , 'USA' , 21.313 , -157.850 ) ;
insert into City values ( 'SFO' , 'San Francisco' , 'CA' , 'USA' , 37.775 ,-122.417) ;
insert into City values ( 'PVD' , 'Providence' , 'RI' , 'USA' , 41.817 , -71.400 ) ;
insert into City values ( 'BOS' , 'Boston' , 'MA' , 'USA' , 42.362 , -71.050 );
insert into City values ( 'DET' , 'Detroit' , 'MI' , 'USA' , 42.323 , -83.167 ) ;
insert into City values ( 'CHI' , 'Chicago' , 'IL' , 'USA' , 41.883 , -87.617 ) ;
insert into City values ( 'ROC' , 'Rochester' , 'NY' , 'USA' , 43.158 , -77.600 ) ;
insert into City values ( 'DAL' , 'Dallas' , 'TX' , 'USA' , 32.777 , -96.800 );
insert into City values ( 'HOU' , 'Houston' , 'TX' , 'USA' , 29.834 , -95.000 ) ;
insert into City values ( 'MIA' , 'Miami' , 'FL' , 'USA' , 25.465 , -80.150 ) ;
insert into City values ( 'CPK' , 'College Park' , 'MD' , 'USA' , 38.987 ,-76.933) ;
insert into City values ( 'YYZ' , 'Toronto' , 'ON' , 'CANADA' , 43.650 , -79.333 ) ;
insert into City values ( 'DEL' , 'Delhi' , 'DE' , 'INDIA' , 28.617 , 77.217 );
insert into City values ( 'PEK' , 'Beijing' , 'BE' , 'CHINA' , 39.917 ,116.417) ;
insert into City values ( 'HKG' , 'Hong Kong' , 'HK' , 'CHINA' , 22.250 ,114.167) ;
insert into City values ( 'TYO' , 'Tokyo' , 'XX' , 'JAPAN' , 35.700 , 139.767 ) ;
insert into City values ( 'LON' , 'London' , 'EN' , 'UK' , 51.500 , -0.167 ) ;
insert into City values ( 'PAR' , 'Paris' , 'XX' , 'FRANCE' , 48.867 , 2.333 );
insert into City values ( 'JNB' , 'Johannesburg' , 'XX' , 'SAFRICA' , -25.550 , 28.000 ) ;
insert into City values ( 'BKK' , 'Bangkok' , 'XX' , 'THAILAND' , 13.733 , 100.500 ) ;
