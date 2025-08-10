[![License](http://img.shields.io/:license-apache%202.0-brightgreen.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)
[![Maven Central](https://maven-badges.herokuapp.com/maven-central/io.debezium/debezium-parent/badge.svg)](http://search.maven.org/#search%7Cga%7C1%7Cg%3A%22io.debezium%22)
[![User chat](https://img.shields.io/badge/chat-users-brightgreen.svg)](https://debezium.zulipchat.com/#narrow/stream/302529-users)
[![Developer chat](https://img.shields.io/badge/chat-devs-brightgreen.svg)](https://debezium.zulipchat.com/#narrow/stream/302533-dev)
[![Google Group](https://img.shields.io/:mailing%20list-debezium-brightgreen.svg)](https://groups.google.com/forum/#!forum/debezium)
[![Stack Overflow](http://img.shields.io/:stack%20overflow-debezium-brightgreen.svg)](http://stackoverflow.com/questions/tagged/debezium)

Copyright Debezium Authors.
Licensed under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).
The Antlr grammars within the debezium-ddl-parser module are licensed under the [MIT License](https://opensource.org/licenses/MIT).

English | [Chinese](README_ZH.md) | [Japanese](README_JA.md) | [Korean](README_KO.md)

# Debezium

Debezium is an open source project that provides a low latency data streaming platform for change data capture (CDC). You set up and configure Debezium to monitor your databases, and then your applications consume events for each row-level change made to the database. Only committed changes are visible, so your application doesn't have to worry about transactions or changes that are rolled back. Debezium provides a single model of all change events, so your application does not have to worry about the intricacies of each kind of database management system. Additionally, since Debezium records the history of data changes in durable, replicated logs, your application can be stopped and restarted at any time, and it will be able to consume all of the events it missed while it was not running, ensuring that all events are processed correctly and completely.

Monitoring databases and being notified when data changes has always been complicated. Relational database triggers can be useful, but are specific to each database and often limited to updating state within the same database (not communicating with external processes). Some databases offer APIs or frameworks for monitoring changes, but there is no standard so each database's approach is different and requires a lot of knowledged and specialized code. It still is very challenging to ensure that all changes are seen and processed in the same order while minimally impacting the database.

Debezium provides modules that do this work for you. Some modules are generic and work with multiple database management systems, but are also a bit more limited in functionality and performance. Other modules are tailored for specific database management systems, so they are often far more capable and they leverage the specific features of the system.

## Basic architecture

Debezium is a change data capture (CDC) platform that achieves its durability, reliability, and fault tolerance qualities by reusing Kafka and Kafka Connect. Each connector deployed to the Kafka Connect distributed, scalable, fault tolerant service monitors a single upstream database server, capturing all of the changes and recording them in one or more Kafka topics (typically one topic per database table). Kafka ensures that all of these data change events are replicated and totally ordered, and allows many clients to independently consume these same data change events with little impact on the upstream system. Additionally, clients can stop consuming at any time, and when they restart they resume exactly where they left off. Each client can determine whether they want exactly-once or at-least-once delivery of all data change events, and all data change events for each database/table are delivered in the same order they occurred in the upstream database.

Applications that don't need or want this level of fault tolerance, performance, scalability, and reliability can instead use Debezium's *embedded connector engine* to run a connector directly within the application space. They still want the same data change events, but prefer to have the connectors send them directly to the application rather than persist them inside Kafka.

## Common use cases

There are a number of scenarios in which Debezium can be extremely valuable, but here we outline just a few of them that are more common.

### Cache invalidation

Automatically invalidate entries in a cache as soon as the record(s) for entries change or are removed. If the cache is running in a separate process (e.g., Redis, Memcache, Infinispan, and others), then the simple cache invalidation logic can be placed into a separate process or service, simplifying the main application. In some situations, the logic can be made a little more sophisticated and can use the updated data in the change events to update the affected cache entries.

### Simplifying monolithic applications

Many applications update a database and then do additional work after the changes are committed: update search indexes, update a cache, send notifications, run business logic, etc. This is often called "dual-writes" since the application is writing to multiple systems outside of a single transaction. Not only is the application logic complex and more difficult to maintain, dual writes also risk losing data or making the various systems inconsistent if the application were to crash after a commit but before some/all of the other updates were performed. Using change data capture, these other activities can be performed in separate threads or separate processes/services when the data is committed in the original database. This approach is more tolerant of failures, does not miss events, scales better, and more easily supports upgrading and operations.

### Sharing databases

When multiple applications share a single database, it is often non-trivial for one application to become aware of the changes committed by another application. One approach is to use a message bus, although non-transactional message busses suffer from the "dual-writes" problems mentioned above. However, this becomes very straightforward with Debezium: each application can monitor the database and react to the changes.

### Data integration

Data is often stored in multiple places, especially when it is used for different purposes and has slightly different forms. Keeping the multiple systems synchronized can be challenging, but simple ETL-type solutions can be implemented quickly with Debezium and simple event processing logic.

### CQRS

The [Command Query Responsibility Separation (CQRS)](http://martinfowler.com/bliki/CQRS.html) architectural pattern uses a one data model for updating and one or more other data models for reading. As changes are recorded on the update-side, those changes are then processed and used to update the various read representations. As a result CQRS applications are usually more complicated, especially when they need to ensure reliable and totally-ordered processing. Debezium and CDC can make this more approachable: writes are recorded as normal, but Debezium captures those changes in durable, totally ordered streams that are consumed by the services that asynchronously update the read-only views. The write-side tables can represent domain-oriented entities, or when CQRS is paired with [Event Sourcing](http://martinfowler.com/eaaDev/EventSourcing.html) the write-side tables are the append-only event log of commands.

## Building Debezium

The following software is required to work with the Debezium codebase and build it locally:

* [Git](https://git-scm.com) 2.2.1 or later
* JDK 21 or later, e.g. [OpenJDK](http://openjdk.java.net/projects/jdk/)
* [Docker Engine](https://docs.docker.com/engine/install/) or [Docker Desktop](https://docs.docker.com/desktop/) 1.9 or later
* [Apache Maven](https://maven.apache.org/index.html) 3.9.8 or later  
  (or invoke the wrapper with `./mvnw` for Maven commands)

See the links above for installation instructions on your platform. You can verify the versions are installed and running:

    $ git --version
    $ javac -version
    $ mvn -version
    $ docker --version

### Why Docker?

Many open source software projects use Git, Java, and Maven, but requiring Docker is less common. Debezium is designed to talk to a number of external systems, such as various databases and services, and our integration tests verify Debezium does this correctly. But rather than expect you have all of these software systems installed locally, Debezium's build system uses Docker to automatically download or create the necessary images and start containers for each of the systems. The integration tests can then use these services and verify Debezium behaves as expected, and when the integration tests finish, Debezium's build will automatically stop any containers that it started.

Debezium also has a few modules that are not written in Java, and so they have to be required on the target operating system. Docker lets our build do this using images with the target operating system(s) and all necessary development tools.

Using Docker has several advantages:

1. You don't have to install, configure, and run specific versions of each external services on your local machine, or have access to them on your local network. Even if you do, Debezium's build won't use them.
1. We can test multiple versions of an external service. Each module can start whatever containers it needs, so different modules can easily use different versions of the services.
1. Everyone can run complete builds locally. You don't have to rely upon a remote continuous integration server running the build in an environment set up with all the required services.
1. All builds are consistent. When multiple developers each build the same codebase, they should see exactly the same results -- as long as they're using the same or equivalent JDK, Maven, and Docker versions. That's because the containers will be running the same versions of the services on the same operating systems. Plus, all of the tests are designed to connect to the systems running in the containers, so nobody has to fiddle with connection properties or custom configurations specific to their local environments.
1. No need to clean up the services, even if those services modify and store data locally. Docker *images* are cached, so reusing them to start containers is fast and consistent. However, Docker *containers* are never reused: they always start in their pristine initial state, and are discarded when they are shutdown. Integration tests rely upon containers, and so cleanup is handled automatically.

### Configure your Docker environment

The Docker Maven Plugin will resolve the docker host by checking the following environment variables:

    export DOCKER_HOST=tcp://10.1.2.2:2376
    export DOCKER_CERT_PATH=/path/to/cdk/.vagrant/machines/default/virtualbox/.docker
    export DOCKER_TLS_VERIFY=1

These can be set automatically if using Docker Machine or something similar.

#### Colima
In order to run testcontainers against [colima](https://github.com/abiosoft/colima) the env vars below should be set (assume we use `default` profile of colima)

    colima start
    export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
    export TESTCONTAINERS_HOST_OVERRIDE="0.0.0.0"
    export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"


### Building the code

First obtain the code by cloning the Git repository:

    $ git clone https://github.com/debezium/debezium.git
    $ cd debezium

Then build the code using Maven:

    $ mvn clean verify

The build starts and uses several Docker containers for different DBMSes. Note that if Docker is not running or configured, you'll likely get an arcane error -- if this is the case, always verify that Docker is running, perhaps by using `docker ps` to list the running containers.

### Don't have Docker running locally for builds?

You can skip the integration tests and docker-builds with the following command:

    $ mvn clean verify -DskipITs

### Building just the artifacts, without running tests, CheckStyle, etc.

You can skip all non-essential plug-ins (tests, integration tests, CheckStyle, formatter, API compatibility check, etc.) using the "quick" build profile:

    $ mvn clean verify -Dquick

This provides the fastest way for solely producing the output artifacts, without running any of the QA related Maven plug-ins.
This comes in handy for producing connector JARs and/or archives as quickly as possible, e.g. for manual testing in Kafka Connect.

### Running tests of the Postgres connector using the wal2json or pgoutput logical decoding plug-ins

The Postgres connector supports three logical decoding plug-ins for streaming changes from the DB server to the connector: decoderbufs (the default), wal2json, and pgoutput.
To run the integration tests of the PG connector using wal2json, enable the "wal2json-decoder" build profile:

    $ mvn clean install -pl :debezium-connector-postgres -Pwal2json-decoder
    
To run the integration tests of the PG connector using pgoutput, enable the "pgoutput-decoder" and "postgres-10" build profiles:

    $ mvn clean install -pl :debezium-connector-postgres -Ppgoutput-decoder,postgres-10

A few tests currently don't pass when using the wal2json plug-in.
Look for references to the types defined in `io.debezium.connector.postgresql.DecoderDifferences` to find these tests.

### Running tests of the Postgres connector with specific Apicurio Version
To run the tests of PG connector using wal2json or pgoutput logical decoding plug-ins with a specific version of Apicurio, a test property can be passed as:

    $ mvn clean install -pl debezium-connector-postgres -Pwal2json-decoder 
          -Ddebezium.test.apicurio.version=1.3.1.Final

In absence of the property the stable version of Apicurio will be fetched.

### Running tests of the Postgres connector against an external database, e.g. Amazon RDS
Please note if you want to test against a *non-RDS* cluster, this test requires `<your user>` to be a superuser with not only `replication` but permissions
to login to `all` databases in `pg_hba.conf`.  It also requires `postgis` packages to be available on the target server for some of the tests to pass.

    $ mvn clean install -pl debezium-connector-postgres -Pwal2json-decoder \
         -Ddocker.skip.build=true -Ddocker.skip.run=true -Dpostgres.host=<your PG host> \
         -Dpostgres.user=<your user> -Dpostgres.password=<your password> \
         -Ddebezium.test.records.waittime=10

Adjust the timeout value as needed.

See [PostgreSQL on Amazon RDS](debezium-connector-postgres/RDS.md) for details on setting up a database on RDS to test against.

### Running tests of the Oracle connector using Oracle XStream

    $ mvn clean install -pl debezium-connector-oracle -Poracle-xstream,oracle-tests -Dinstantclient.dir=<path-to-instantclient>

### Running tests of the Oracle connector with a non-CDB database

    $ mvn clean install -pl debezium-connector-oracle -Poracle-tests -Dinstantclient.dir=<path-to-instantclient> -Ddatabase.pdb.name=

### Running the tests for MongoDB with oplog capturing from an IDE

When running the test without maven, please make sure you pass the correct parameters to the execution. Look for the correct parameters in `.github/workflows/mongodb-oplog-workflow.yml` and
append them to the JVM execution parameters, prefixing them with `debezium.test`. As the execution will happen outside of the lifecycle execution, you need to start the MongoDB container manually
from the MongoDB connector directory

    $ mvn docker:start -B -am -Passembly -Dcheckstyle.skip=true -Dformat.skip=true -Drevapi.skip -Dcapture.mode=oplog -Dversion.mongo.server=3.6 -Dorg.slf4j.simpleLogger.log.org.apache.maven.cli.transfer.Slf4jMavenTransferListener=warn -Dmaven.wagon.http.pool=false -Dmaven.wagon.httpconnectionManager.ttlSeconds=120 -Dcapture.mode=oplog -Dmongo.server=3.6

The relevant portion of the line will look similar to the following:

    java -ea -Ddebezium.test.capture.mode=oplog -Ddebezium.test.version.mongo.server=3.6 -Djava.awt.headless=true -Dconnector.mongodb.members.auto.discover=false -Dconnector.mongodb.name=mongo1 -DskipLongRunningTests=true [...]

## Contributing

The Debezium community welcomes anyone that wants to help out in any way, whether that includes reporting problems, helping with documentation, or contributing code changes to fix bugs, add tests, or implement new features. See [this document](CONTRIBUTE.md) for details.

A big thank you to all the Debezium contributors!

<a href="https://github.com/debezium/debezium/graphs/contributors">
  <img src="https://contributors-img.web.app/image?repo=debezium/debezium" />
</a>

# Oracle归档日志智能分段处理器

## 概述

Oracle归档日志智能分段处理器是一个高性能的Python工具，用于解决Oracle归档日志并行处理的性能瓶颈。通过智能分段算法，它能够将大批量的归档日志数据分成多个均匀的段，然后并行处理，显著提高处理效率。

## 核心特性

### 🎯 智能分段算法
- **自适应分段**: 基于SCN范围内记录密度的采样估算，动态调整分段策略
- **负载均衡**: 确保每个分段的记录数尽可能接近目标值，避免负载不均
- **二分查找优化**: 使用二分查找算法精确定位分段边界

### 🚀 高性能并行处理
- **多线程处理**: 支持多线程并行处理各个分段
- **批量处理**: 内置批量处理机制，减少I/O开销
- **连接池**: 支持数据库连接池，提高连接复用率

### 📊 智能监控与统计
- **实时统计**: 提供详细的处理统计信息和性能指标
- **准确性监控**: 跟踪分段估算的准确性，持续优化算法
- **进度监控**: 实时显示处理进度和各分段状态

## 安装

### 环境要求
- Python 3.7+
- Oracle Database 11g+ (支持LogMiner)
- Oracle Instant Client

### 安装步骤

1. 安装Python依赖:
```bash
pip install -r requirements.txt
```

2. 配置Oracle Instant Client (根据您的操作系统):
```bash
# Linux/macOS
export LD_LIBRARY_PATH=/path/to/instantclient:$LD_LIBRARY_PATH

# Windows
set PATH=C:\path\to\instantclient;%PATH%
```

3. 确保Oracle用户具有LogMiner权限:
```sql
GRANT EXECUTE ON DBMS_LOGMNR TO your_user;
GRANT EXECUTE ON DBMS_LOGMNR_D TO your_user;
GRANT SELECT ON V_$LOGMNR_CONTENTS TO your_user;
GRANT SELECT ON V_$LOGMNR_LOGS TO your_user;
```

## 快速开始

### 基础使用

```python
from oracle_log_segmentation import (
    OracleLogSegmentProcessor, 
    SegmentationConfig
)
import cx_Oracle

# 1. 配置数据库连接
def create_connection():
    return cx_Oracle.connect(
        user='your_user',
        password='your_password',
        dsn='localhost:1521/ORCL'
    )

# 2. 配置LogMiner设置
def setup_logminer(archive_log_file):
    return f"""
    BEGIN
        DBMS_LOGMNR.ADD_LOGFILE(
            LOGFILENAME => '{archive_log_file}',
            OPTIONS => DBMS_LOGMNR.NEW
        );
        DBMS_LOGMNR.START_LOGMNR(
            OPTIONS => DBMS_LOGMNR.SKIP_CORRUPTION
        );
    END;
    """

# 3. 定义记录处理函数
def process_records(records):
    for record in records:
        print(f"处理操作: {record['operation']} on {record['table_name']}")
        # 在这里实现您的业务逻辑

# 4. 创建并使用处理器
config = SegmentationConfig(
    target_records_per_segment=100000,  # 每段10万条记录
    max_segments=8,                     # 最多8个分段
    sampling_ratio=0.001                # 0.1%采样率
)

processor = OracleLogSegmentProcessor(
    connection_factory=create_connection,
    logminer_setup_sql=setup_logminer('/path/to/archive.log'),
    config=config
)

# 5. 并行处理归档日志
stats = processor.process_archive_log_parallel(
    start_scn=1000,
    end_scn=100000,
    record_processor=process_records,
    max_workers=4
)

print(f"处理完成: {stats['total_records']}条记录，耗时{stats['total_time']:.2f}秒")
```

## 配置参数详解

### SegmentationConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target_records_per_segment` | int | 100000 | 每个分段的目标记录数 |
| `max_segments` | int | 20 | 最大分段数限制 |
| `min_segments` | int | 2 | 最小分段数限制 |
| `sampling_ratio` | float | 0.001 | 采样比例（0.1%） |
| `max_sampling_records` | int | 10000 | 最大采样记录数 |
| `tolerance_ratio` | float | 0.3 | 容差比例（30%） |

### 性能调优建议

#### 1. 分段策略优化
```python
# 大数据量场景（百万级记录）
config = SegmentationConfig(
    target_records_per_segment=200000,  # 增大分段大小
    max_segments=16,                    # 增加最大分段数
    sampling_ratio=0.0005,              # 降低采样率减少开销
    tolerance_ratio=0.4                 # 放宽容差提高分段速度
)

# 小数据量场景（十万级记录）
config = SegmentationConfig(
    target_records_per_segment=50000,   # 减小分段大小
    max_segments=6,                     # 减少分段数
    sampling_ratio=0.002,               # 提高采样率保证准确性
    tolerance_ratio=0.2                 # 严格控制分段均匀性
)
```

#### 2. 并行度配置
```python
import os

# 根据CPU核心数自动配置
max_workers = min(os.cpu_count(), len(segments))

# 考虑数据库连接数限制
max_workers = min(max_workers, 8)  # 通常不超过8个并发连接
```

#### 3. 内存优化
```python
def memory_efficient_processor(records):
    # 流式处理，避免大量数据在内存中积累
    for record in records:
        # 立即处理并释放
        process_single_record(record)
        
    # 定期触发垃圾回收
    if len(records) > 10000:
        import gc
        gc.collect()
```

## 高级用法

### 1. 自定义分段策略

```python
class CustomSegmentationAlgorithm(AdaptiveSegmentationAlgorithm):
    def create_segments(self, start_scn, end_scn):
        # 实现您的自定义分段逻辑
        # 例如：基于时间窗口分段、基于表名分段等
        pass
```

### 2. 错误处理和重试

```python
def robust_processor(records):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 处理记录
            process_records_batch(records)
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"处理失败，已达到最大重试次数: {e}")
                raise
            logger.warning(f"处理失败，正在重试 ({attempt + 1}/{max_retries}): {e}")
            time.sleep(2 ** attempt)  # 指数退避
```

### 3. 结果持久化

```python
def persistent_processor(records):
    # 批量写入数据库
    connection = get_target_connection()
    cursor = connection.cursor()
    
    batch_data = []
    for record in records:
        batch_data.append((
            record['scn'],
            record['timestamp'],
            record['operation'],
            record['table_name'],
            record['sql_redo']
        ))
    
    cursor.executemany("""
        INSERT INTO processed_changes 
        (scn, timestamp, operation, table_name, sql_redo)
        VALUES (?, ?, ?, ?, ?)
    """, batch_data)
    
    connection.commit()
    cursor.close()
```

## 监控和告警

### 1. 性能监控

```python
def monitoring_processor(records):
    start_time = time.time()
    
    # 处理记录
    process_records(records)
    
    processing_time = time.time() - start_time
    records_per_second = len(records) / processing_time
    
    # 性能告警
    if records_per_second < 1000:  # 低于1000条/秒
        logger.warning(f"处理速度较慢: {records_per_second:.1f} 条/秒")
    
    # 记录性能指标
    metrics.gauge('processing.records_per_second', records_per_second)
    metrics.gauge('processing.batch_size', len(records))
```

### 2. 数据质量监控

```python
def quality_monitoring_processor(records):
    error_count = 0
    warning_count = 0
    
    for record in records:
        # 检查数据完整性
        if not record.get('scn'):
            error_count += 1
            logger.error(f"记录缺少SCN: {record}")
            continue
            
        # 检查可疑操作
        if record['operation'] == 'DELETE' and 'CRITICAL' in record['table_name']:
            warning_count += 1
            logger.warning(f"关键表删除操作: {record['table_name']} at SCN {record['scn']}")
    
    # 质量报告
    total_records = len(records)
    error_rate = error_count / total_records if total_records > 0 else 0
    
    if error_rate > 0.01:  # 错误率超过1%
        logger.error(f"数据质量告警: 错误率 {error_rate:.2%}")
```

## 常见问题解决

### Q1: 分段不均匀怎么办？
**A**: 调整采样参数：
- 增加 `sampling_ratio` 提高采样准确性
- 减少 `tolerance_ratio` 严格控制分段均匀性
- 增加采样点数量（在代码中修改 `sample_points`）

### Q2: 处理速度慢怎么办？
**A**: 性能优化策略：
- 增加 `max_workers` 提高并行度
- 减少 `sampling_ratio` 降低采样开销
- 优化记录处理函数，避免复杂计算
- 使用批量处理和连接池

### Q3: 内存占用过高怎么办？
**A**: 内存优化措施：
- 减少 `target_records_per_segment` 降低单段内存占用
- 在处理函数中及时释放大对象
- 使用流式处理避免数据积累
- 定期调用 `gc.collect()`

### Q4: LogMiner权限不足怎么办？
**A**: 权限配置：
```sql
-- 以DBA身份执行
GRANT EXECUTE ON DBMS_LOGMNR TO your_user;
GRANT EXECUTE ON DBMS_LOGMNR_D TO your_user;
GRANT SELECT ON V_$LOGMNR_CONTENTS TO your_user;
GRANT SELECT ON V_$LOGMNR_LOGS TO your_user;
GRANT SELECT ON V_$ARCHIVED_LOG TO your_user;
```

## 最佳实践

1. **预分析**: 处理前先分析归档日志的SCN范围和记录分布
2. **测试验证**: 在小范围数据上测试分段效果
3. **监控调优**: 持续监控处理性能，根据实际情况调整参数
4. **错误处理**: 实现完善的错误处理和重试机制
5. **资源管理**: 合理控制并发数，避免对数据库造成过大压力

## 许可证

MIT License

## 贡献指南

欢迎提交Issue和Pull Request来改进这个项目！

## 联系支持

如果您在使用过程中遇到问题，请：
1. 查看常见问题解决部分
2. 提交Issue描述具体问题
3. 提供错误日志和配置信息
