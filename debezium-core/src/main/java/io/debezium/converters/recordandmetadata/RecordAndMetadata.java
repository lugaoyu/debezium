/*
 * Copyright Debezium Authors.
 *
 * Licensed under the Apache Software License version 2.0, available at http://www.apache.org/licenses/LICENSE-2.0
 */

package io.debezium.converters.recordandmetadata;

import java.util.Set;

import org.apache.kafka.connect.data.Schema;
import org.apache.kafka.connect.data.SchemaAndValue;
import org.apache.kafka.connect.data.Struct;

/**
 * Common interface for a structure containing a record and its metadata
 *
 * @author Roman Kudryashov
 */
public interface RecordAndMetadata {

    String id();

    String type();

    Struct source();

    String operation();

    Struct transaction();

    SchemaAndValue timestamp();

    String traceParent();

    String dataSchemaName();

    Schema dataSchema(String... dataFields);

    Struct data(String... dataFields);

    String connectorType();

    Object sourceField(String name, Set<String> connectorSpecificSourceFields);
}
