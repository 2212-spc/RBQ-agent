# L0 QUERY_FAIL Sample Diagnosis

- Sample size: `20`
- Selection summary: `{'wrong': 20}`
- Query diff summary: `{'整体结构/源列选择错误': 19, '未形成有效查询结构': 1}`
- Bare LLM summary: `{'llm_fail': 4, 'llm_pass': 16}`

## spider__bike_1__00163 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `False` (QUERY_FAIL)

选源细节：
- `{'slot_id': 'slot_id', 'selected_source_table': 'station', 'selected_column': 'id', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.id FROM trip AS T1 JOIN station AS T2 ON T1.start_station_id  =  T2.id ORDER BY T2.dock_count DESC LIMIT 1
```

Pred SQL:
```sql
SELECT t0."id" AS "id" FROM "canon_0" AS t0
```

## spider__driving_school__06657 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `False` (INSTANCE_FAIL)

选源细节：
- `{'slot_id': 'slot_state_province_county', 'selected_source_table': 'Staff', 'selected_column': 'staff_address_id', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.state_province_county FROM Addresses AS T1 JOIN Staff AS T2 ON T1.address_id = T2.staff_address_id GROUP BY T1.state_province_county HAVING count(*) BETWEEN 2 AND 4;
```

Pred SQL:
```sql
SELECT t0."state_province_county" AS "state_province_county" FROM "canon_0" AS t0
```

## spider__workshop_paper__05833 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_author', 'selected_source_table': 'submission', 'selected_column': 'Author', 'status': 'wrong'}`
- `{'slot_id': 'slot_result', 'selected_source_table': 'submission', 'selected_column': 'Author', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T2.Author ,  T1.Result FROM acceptance AS T1 JOIN submission AS T2 ON T1.Submission_ID  =  T2.Submission_ID
```

Pred SQL:
```sql
SELECT t1."Author" AS "Author", t1."Result" AS "Result" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t1."__join_0_left" = t0."__join_0_right"
```

## spider__entrepreneur__02273 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `False` (QUERY_FAIL)

选源细节：
- `{'slot_id': 'slot_name', 'selected_source_table': 'people', 'selected_column': 'Name', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T2.Name FROM entrepreneur AS T1 JOIN people AS T2 ON T1.People_ID  =  T2.People_ID
```

Pred SQL:
```sql
SELECT t0."Name" AS "Name" FROM "canon_0" AS t0
```

## spider__inn_1__02601 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_decor', 'selected_source_table': 'Rooms', 'selected_column': 'decor', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T2.decor FROM Reservations AS T1 JOIN Rooms AS T2 ON T1.Room  =  T2.RoomId GROUP BY T2.decor ORDER BY count(T2.decor) ASC LIMIT 1;
```

Pred SQL:
```sql
SELECT t1."decor" AS "decor" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t1."__join_0_left" = t0."__join_0_right" GROUP BY t1."decor" ORDER BY COUNT(*) ASC LIMIT 1
```

## spider__local_govt_mdm__02650 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_source_system_code', 'selected_source_table': 'CMI_Cross_References', 'selected_column': 'source_system_code', 'status': 'wrong'}`
- `{'slot_id': 'slot_master_customer_id', 'selected_source_table': 'Parking_Fines', 'selected_column': 'council_tax_id', 'status': 'wrong'}`
- `{'slot_id': 'slot_council_tax_id', 'selected_source_table': 'Parking_Fines', 'selected_column': 'council_tax_id', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.source_system_code ,  T1.master_customer_id ,  T2.council_tax_id FROM CMI_Cross_References AS T1 JOIN Parking_Fines AS T2 ON T1.cmi_cross_ref_id  =  T2.cmi_cross_ref_id
```

Pred SQL:
```sql
SELECT t0."source_system_code" AS "source_system_code", t1."master_customer_id" AS "master_customer_id", t1."council_tax_id" AS "council_tax_id" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t0."__join_0_left" = t1."__join_0_right"
```

## spider__sports_competition__03355 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_name', 'selected_source_table': 'club', 'selected_column': 'name', 'status': 'wrong'}`
- `{'slot_id': 'slot_player_id', 'selected_source_table': 'club', 'selected_column': 'Club_ID', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.name ,  T2.Player_id FROM club AS T1 JOIN player AS T2 ON T1.Club_ID  =  T2.Club_ID
```

Pred SQL:
```sql
SELECT t0."name" AS "name", t0."Player_ID" AS "Player_ID" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t0."__join_0_left" = t1."__join_0_right"
```

## spider__county_public_safety__02553 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_white', 'selected_source_table': 'county_public_safety', 'selected_column': 'Name', 'status': 'wrong'}`
- `{'slot_id': 'slot_crime_rate', 'selected_source_table': 'county_public_safety', 'selected_column': 'Crime_rate', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.White ,  T2.Crime_rate FROM city AS T1 JOIN county_public_safety AS T2 ON T1.County_ID  =  T2.County_ID
```

Pred SQL:
```sql
SELECT t1."White" AS "White", t1."Crime_rate" AS "Crime_rate" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t0."__join_0_left" = t1."__join_0_right"
```

## spider__ship_mission__04018 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_code', 'selected_source_table': 'mission', 'selected_column': 'Code', 'status': 'wrong'}`
- `{'slot_id': 'slot_fate', 'selected_source_table': 'ship', 'selected_column': 'Name', 'status': 'wrong'}`
- `{'slot_id': 'slot_name', 'selected_source_table': 'ship', 'selected_column': 'Name', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.Code ,  T1.Fate ,  T2.Name FROM mission AS T1 JOIN ship AS T2 ON T1.Ship_ID  =  T2.Ship_ID
```

Pred SQL:
```sql
SELECT t0."Code" AS "Code", t1."Fate" AS "Fate", t1."Name" AS "Name" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t0."__join_0_left" = t1."__join_0_right"
```

## spider__local_govt_mdm__02649 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_source_system_code', 'selected_source_table': 'Benefits_Overpayments', 'selected_column': 'council_tax_id', 'status': 'wrong'}`
- `{'slot_id': 'slot_council_tax_id', 'selected_source_table': 'Benefits_Overpayments', 'selected_column': 'council_tax_id', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.source_system_code ,  T2.council_tax_id FROM CMI_Cross_References AS T1 JOIN Benefits_Overpayments AS T2 ON T1.cmi_cross_ref_id  =  T2.cmi_cross_ref_id ORDER BY T2.council_tax_id
```

Pred SQL:
```sql
SELECT t0."source_system_code" AS "source_system_code", t0."council_tax_id" AS "council_tax_id" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t1."__join_0_left" = t0."__join_0_right"
```

## spider__book_2__00222 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_title', 'selected_source_table': 'book', 'selected_column': 'Title', 'status': 'wrong'}`
- `{'slot_id': 'slot_publication_date', 'selected_source_table': 'book', 'selected_column': 'Book_ID', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.Title ,  T2.Publication_Date FROM book AS T1 JOIN publication AS T2 ON T1.Book_ID  =  T2.Book_ID
```

Pred SQL:
```sql
SELECT t0."Title" AS "Title", t0."Publication_Date" AS "Publication_Date" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t0."__join_0_left" = t1."__join_0_right"
```

## spider__pilot_record__02094 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_fleet_series', 'selected_source_table': 'aircraft', 'selected_column': 'Fleet_Series', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T2.Fleet_Series FROM pilot_record AS T1 JOIN aircraft AS T2 ON T1.Aircraft_ID  =  T2.Aircraft_ID JOIN pilot AS T3 ON T1.Pilot_ID  =  T3.Pilot_ID WHERE T3.Age  <  34
```

Pred SQL:
```sql
SELECT t0."Fleet_Series" AS "Fleet_Series" FROM "canon_0" AS t0
```

## spider__workshop_paper__05832 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_author', 'selected_source_table': 'submission', 'selected_column': 'Author', 'status': 'wrong'}`
- `{'slot_id': 'slot_result', 'selected_source_table': 'submission', 'selected_column': 'Author', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T2.Author ,  T1.Result FROM acceptance AS T1 JOIN submission AS T2 ON T1.Submission_ID  =  T2.Submission_ID
```

Pred SQL:
```sql
SELECT t1."Author" AS "Author", t1."Result" AS "Result" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t1."__join_0_left" = t0."__join_0_right"
```

## spider__county_public_safety__02552 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_white', 'selected_source_table': 'county_public_safety', 'selected_column': 'Name', 'status': 'wrong'}`
- `{'slot_id': 'slot_crime_rate', 'selected_source_table': 'county_public_safety', 'selected_column': 'Crime_rate', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.White ,  T2.Crime_rate FROM city AS T1 JOIN county_public_safety AS T2 ON T1.County_ID  =  T2.County_ID
```

Pred SQL:
```sql
SELECT t1."White" AS "White", t1."Crime_rate" AS "Crime_rate" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t0."__join_0_left" = t1."__join_0_right"
```

## spider__riding_club__01728 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_player_name', 'selected_source_table': 'player', 'selected_column': 'Player_name', 'status': 'wrong'}`
- `{'slot_id': 'slot_coach_name', 'selected_source_table': 'player', 'selected_column': 'Sponsor_name', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T3.Player_name ,  T2.coach_name FROM player_coach AS T1 JOIN coach AS T2 ON T1.Coach_ID  =  T2.Coach_ID JOIN player AS T3 ON T1.Player_ID  =  T3.Player_ID
```

Pred SQL:
```sql
SELECT t1."Player_name" AS "Player_name", t1."Coach_name" AS "Coach_name" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t1."__join_0_left" = t0."__join_0_right"
```

## spider__baseball_1__03666 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_max_t1_wins', 'selected_source_table': 'postseason', 'selected_column': 'round', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT max(T1.wins) FROM postseason AS T1 JOIN team AS T2 ON T1.team_id_winner  =  T2.team_id_br WHERE T2.name  =  'Boston Red Stockings';
```

Pred SQL:
```sql
SELECT t0."max(T1.wins)" AS "max(T1.wins)" FROM "canon_0" AS t0
```

## spider__tracking_share_transactions__05880 / A

- 选源选列判断: `wrong`
- 查询差异类型: `未形成有效查询结构`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_investor_id', 'selected_source_table': 'INVESTORS', 'selected_column': 'investor_id', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T2.investor_id FROM INVESTORS AS T1 JOIN TRANSACTIONS AS T2 ON T1.investor_id  =  T2.investor_id GROUP BY T2.investor_id HAVING COUNT(*)  >=  2
```

Pred SQL:
```sql

```

## spider__wrestler__01856 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_name', 'selected_source_table': 'elimination', 'selected_column': 'Team', 'status': 'wrong'}`
- `{'slot_id': 'slot_elimination_move', 'selected_source_table': 'elimination', 'selected_column': 'Elimination_Move', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T2.Name ,  T1.Elimination_Move FROM elimination AS T1 JOIN wrestler AS T2 ON T1.Wrestler_ID  =  T2.Wrestler_ID
```

Pred SQL:
```sql
SELECT t0."Name" AS "Name", t0."Elimination_Move" AS "Elimination_Move" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t1."__join_0_left" = t0."__join_0_right"
```

## spider__film_rank__04130 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `True` (PASS)

选源细节：
- `{'slot_id': 'slot_title', 'selected_source_table': 'film', 'selected_column': 'Title', 'status': 'wrong'}`
- `{'slot_id': 'slot_type', 'selected_source_table': 'film', 'selected_column': 'Title', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T1.Title ,  T2.Type FROM film AS T1 JOIN film_market_estimation AS T2 ON T1.Film_ID  =  T2.Film_ID
```

Pred SQL:
```sql
SELECT t0."Title" AS "Title", t0."Type" AS "Type" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t0."__join_0_left" = t1."__join_0_right"
```

## spider__railway__05640 / A

- 选源选列判断: `wrong`
- 查询差异类型: `整体结构/源列选择错误`
- bare LLM(l0) 是否通过: `False` (QUERY_FAIL)

选源细节：
- `{'slot_id': 'slot_name', 'selected_source_table': 'train', 'selected_column': 'Name', 'status': 'wrong'}`
- `{'slot_id': 'slot_location', 'selected_source_table': 'railway', 'selected_column': 'Location', 'status': 'wrong'}`

Gold SQL:
```sql
SELECT T2.Name ,  T1.Location FROM railway AS T1 JOIN train AS T2 ON T1.Railway_ID  =  T2.Railway_ID
```

Pred SQL:
```sql
SELECT t1."Name" AS "Name", t0."Location" AS "Location" FROM "canon_0" AS t0 JOIN "canon_1" AS t1 ON t1."__join_0_left" = t0."__join_0_right"
```
