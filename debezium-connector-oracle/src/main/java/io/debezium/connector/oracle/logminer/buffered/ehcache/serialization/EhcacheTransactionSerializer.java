/*
 * Copyright Debezium Authors.
 *
 * Licensed under the Apache Software License version 2.0, available at http://www.apache.org/licenses/LICENSE-2.0
 */
package io.debezium.connector.oracle.logminer.buffered.ehcache.serialization;

import java.io.IOException;
import java.time.Instant;

import org.ehcache.spi.serialization.Serializer;

import io.debezium.connector.oracle.Scn;
import io.debezium.connector.oracle.logminer.buffered.ehcache.EhcacheTransaction;

/**
 * An Ehcache {@link Serializer} implementation for storing an {@link EhcacheTransaction} in the cache.
 *
 * @author Chris Cranford
 */
public class EhcacheTransactionSerializer extends AbstractEhcacheSerializer<EhcacheTransaction> {

    public EhcacheTransactionSerializer(ClassLoader classLoader) {
    }

    @Override
    protected void serialize(EhcacheTransaction object, SerializerOutputStream stream) throws IOException {
        stream.writeString(object.getTransactionId());
        stream.writeScn(object.getStartScn());
        stream.writeInstant(object.getChangeTime());
        stream.writeString(object.getUserName());
        stream.writeInt(object.getRedoThreadId());
        stream.writeInt(object.getNumberOfEvents());
        stream.writeString(object.getClientId());
    }

    @Override
    protected EhcacheTransaction deserialize(SerializerInputStream stream) throws IOException {
        final String transactionId = stream.readString();
        final Scn startScn = readScn(stream.readString());
        final Instant changeTime = stream.readInstant();
        final String userName = stream.readString();
        final int redoThread = stream.readInt();
        final int numberOfEvents = stream.readInt();
        final String clientId = stream.readString();
        return new EhcacheTransaction(transactionId, startScn, changeTime, userName, redoThread, numberOfEvents, clientId);
    }

    private Scn readScn(String value) {
        return value.equals("null") ? Scn.NULL : Scn.valueOf(value);
    }
}
