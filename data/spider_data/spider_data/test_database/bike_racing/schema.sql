PRAGMA foreign_keys=ON;
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "bike" (
    "id" int,
    "product_name" text,
    "weight" int,
    "price" real,
    "material" text,
    primary key("id")
);
INSERT INTO bike VALUES(1,'BIANCHI SPECIALISSIMA',780,9998.9999999999999999,'Carbon CC');
INSERT INTO bike VALUES(2,'CANNONDALE SUPERSIX EVO HI-MOD DURA ACE',850,5329.9999999999999999,'carbon fiber');
INSERT INTO bike VALUES(3,'CANYON AEROAD CF SLX 8.0 DI2',880,3049.9999999999999999,'Toray T700 and T800 carbon fiber');
INSERT INTO bike VALUES(4,'GIANT TCR ADVANCED SL 0',750,9000.0,'Carbon CC');
INSERT INTO bike VALUES(5,'Ibis',800,3598.9999999999999998,'Carbon CC');
INSERT INTO bike VALUES(6,'Ibis ||',760,5000, 'carbon fiber');
CREATE TABLE IF NOT EXISTS "cyclist" (
    "id" int,
    "heat" int,
    "name" text,
    "nation" text,
    "result" real,
    primary key("id")
);
INSERT INTO cyclist VALUES(1,4,'Bradley Wiggins','Great Britain','4:16.571');
INSERT INTO cyclist VALUES(2,3,'Hayden Roulston','New Zealand','4:19.232');
INSERT INTO cyclist VALUES(3,1,'Steven Burke','Great Britain','4:21.558');
INSERT INTO cyclist VALUES(4,2,'Alexei Markov','Russia','4:22.308');
INSERT INTO cyclist VALUES(5,1,'Volodymyr Dyudya','Ukraine','4:22.471');
INSERT INTO cyclist VALUES(6,2,'Antonio Tauler','Spain','4:24.974');
INSERT INTO cyclist VALUES(7,4,'Alexander Serov','Russia','4:25.391');
INSERT INTO cyclist VALUES(8,3,'Taylor Phinney','United States','4:26.644');
CREATE TABLE IF NOT EXISTS "cyclists_own_bikes" (
    "cyclist_id" int,
    "bike_id" int,
    "purchase_year" int,
    primary key("cyclist_id", "bike_id"),
    foreign key("cyclist_id") references `cyclist`("id"),
    foreign key("bike_id") references `bike`("id")
);
INSERT INTO cyclists_own_bikes VALUES(1,2,2011);
INSERT INTO cyclists_own_bikes VALUES(1,3,2015);
INSERT INTO cyclists_own_bikes VALUES(2,3,2017);
INSERT INTO cyclists_own_bikes VALUES(2,5,2013);
INSERT INTO cyclists_own_bikes VALUES(2,4,2018);
INSERT INTO cyclists_own_bikes VALUES(3,4,2017);
INSERT INTO cyclists_own_bikes VALUES(4,4,2017);
INSERT INTO cyclists_own_bikes VALUES(5,5,2016);
INSERT INTO cyclists_own_bikes VALUES(6,5,2016);
INSERT INTO cyclists_own_bikes VALUES(7,5,2010);
INSERT INTO cyclists_own_bikes VALUES(7,4,2011);
INSERT INTO cyclists_own_bikes VALUES(7,2,2012);
INSERT INTO cyclists_own_bikes VALUES(7,1,2013);
INSERT INTO cyclists_own_bikes VALUES(7,3,2014);
COMMIT;

