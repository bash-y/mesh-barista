# System Architecture

```
  Phones on the Wi-Fi ──► http://barista.io   (every node is an access point serving the same dashboard)
        ┆                        ┆                        ┆
 ┌──────┴───────┐  ESP-NOW  ┌────┴──────────┐  ESP-NOW  ┌─┴────────────┐
 │ Node 1       │◄────────►│ Node 2        │◄────────►│ Node 3       │
 │ Pump station │           │ Control center│           │ Output       │
 └──────┬───────┘           └───────────────┘           └──────┬───────┘
        ▲      cup at 90 % → Node 1 stops the pump (relayed if out of range)     │
        └────────────────────────────────────────────────────────────────────────┘
 Reservoirs (coffee · milk · cream) ══ pump → tubing ══►  Cup
```

## Nodes

<!-- include: README.md#Nodes -->

## Radio and messages

- **ESP-NOW broadcast** on channel 1: no router and no pairing. Every node hears every frame in range.
- **One-hop relay:** a node rebroadcasts each message it hears first-hand once, so a node out of range of
  another is still reached.
- **Sequence numbers** drop repeats. **Heartbeat** every second; a node not heard for 3 s is lost.
- **JSON messages** carry node, zone, seq, uptime, readings and state. The largest (a full order queue)
  is about 225 bytes; one ESP-NOW frame holds 250.

## Where decisions are made

Each node that owns an actuator decides locally. Node 1 owns the pumps, so Node 1 stops them: when Node 3
reports the cup at 90 %, when its own reservoir is too low, when the cup reading is stale, or when it
loses Node 2 or Node 3. See [[Safety Logic]].

## Dashboard

Every node is a Wi-Fi access point with the same name and address and serves the same page, so the
dashboard survives the loss of any one node. See [[Dashboard and Orders]].
