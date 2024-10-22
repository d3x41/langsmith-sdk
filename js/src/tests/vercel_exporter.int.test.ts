import { openai } from "@ai-sdk/openai";

import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { z } from "zod";
import { LangSmithAISDKExporter } from "../wrappers/vercel.js";
import { v4 as uuid } from "uuid";
import {
  generateText,
  streamText,
  generateObject,
  streamObject,
  embed,
  embedMany,
} from "ai";
import { tool } from "ai";
import { gatherIterator } from "./utils/iterator.js";
import { Client } from "../index.js";
import { waitUntilRunFound } from "./utils.js";

const getTelemetrySettings = (langsmithRunId?: string) => {
  const metadata: Record<string, string> = {
    userId: "123",
    language: "english",
  };

  if (langsmithRunId) metadata.langsmithRunId = langsmithRunId;
  return {
    isEnabled: true,
    functionId: "functionId",
    metadata,
  };
};

const client = new Client();
// Not using @opentelemetry/sdk-node because we need to force flush
// the spans to ensure they are sent to LangSmith between tests
const provider = new NodeTracerProvider();
provider.addSpanProcessor(
  new BatchSpanProcessor(new LangSmithAISDKExporter({ client }))
);
provider.register();

test("generateText", async () => {
  const traceId = uuid();

  await generateText({
    model: openai("gpt-4o-mini"),
    messages: [
      {
        role: "user",
        content: "What are my orders and where are they? My user ID is 123",
      },
    ],
    tools: {
      listOrders: tool({
        description: "list all orders",
        parameters: z.object({ userId: z.string() }),
        execute: async ({ userId }) =>
          `User ${userId} has the following orders: 1`,
      }),
      viewTrackingInformation: tool({
        description: "view tracking information for a specific order",
        parameters: z.object({ orderId: z.string() }),
        execute: async ({ orderId }) =>
          `Here is the tracking information for ${orderId}`,
      }),
    },
    experimental_telemetry: getTelemetrySettings(traceId),
    maxSteps: 10,
  });

  await provider.forceFlush();
  await waitUntilRunFound(client, traceId, true);

  const storedRun = await client.readRun(traceId);
  expect(storedRun.id).toEqual(traceId);
});

test("generateText with image", async () => {
  const traceId = uuid();
  await generateText({
    model: openai("gpt-4o-mini"),
    messages: [
      {
        role: "user",
        content: [
          {
            type: "text",
            text: "What's in this picture?",
          },
          {
            type: "image",
            image: new URL("https://picsum.photos/200/300"),
          },
        ],
      },
    ],
    experimental_telemetry: getTelemetrySettings(traceId),
  });

  await provider.forceFlush();
  await waitUntilRunFound(client, traceId, true);

  const storedRun = await client.readRun(traceId);
  expect(storedRun.id).toEqual(traceId);
});

test("streamText", async () => {
  const traceId = uuid();
  const result = await streamText({
    model: openai("gpt-4o-mini"),
    messages: [
      {
        role: "user",
        content: "What are my orders and where are they? My user ID is 123",
      },
    ],
    tools: {
      listOrders: tool({
        description: "list all orders",
        parameters: z.object({ userId: z.string() }),
        execute: async ({ userId }) =>
          `User ${userId} has the following orders: 1`,
      }),
      viewTrackingInformation: tool({
        description: "view tracking information for a specific order",
        parameters: z.object({ orderId: z.string() }),
        execute: async ({ orderId }) =>
          `Here is the tracking information for ${orderId}`,
      }),
    },
    experimental_telemetry: getTelemetrySettings(traceId),
    maxSteps: 10,
  });

  await gatherIterator(result.fullStream);
  await provider.forceFlush();
  await waitUntilRunFound(client, traceId, true);

  const storedRun = await client.readRun(traceId);
  expect(storedRun.id).toEqual(traceId);
});

test("generateObject", async () => {
  const traceId = uuid();
  await generateObject({
    model: openai("gpt-4o-mini", { structuredOutputs: true }),
    schema: z.object({
      recipe: z.object({
        city: z.string(),
        unit: z.union([z.literal("celsius"), z.literal("fahrenheit")]),
      }),
    }),
    prompt: "What's the weather in Prague?",
    experimental_telemetry: getTelemetrySettings(traceId),
  });

  await provider.forceFlush();
  await waitUntilRunFound(client, traceId, true);

  const storedRun = await client.readRun(traceId);
  expect(storedRun.id).toEqual(traceId);
});

test("streamObject", async () => {
  const traceId = uuid();
  const result = await streamObject({
    model: openai("gpt-4o-mini", { structuredOutputs: true }),
    schema: z.object({
      recipe: z.object({
        city: z.string(),
        unit: z.union([z.literal("celsius"), z.literal("fahrenheit")]),
      }),
    }),
    prompt: "What's the weather in Prague?",
    experimental_telemetry: getTelemetrySettings(traceId),
  });

  await gatherIterator(result.partialObjectStream);
  await provider.forceFlush();
  await waitUntilRunFound(client, traceId, true);

  const storedRun = await client.readRun(traceId);
  expect(storedRun.id).toEqual(traceId);
});

test("embed", async () => {
  const traceId = uuid();
  await embed({
    model: openai.embedding("text-embedding-3-small"),
    value: "prague castle at sunset",
    experimental_telemetry: getTelemetrySettings(traceId),
  });

  await provider.forceFlush();
  await waitUntilRunFound(client, traceId, true);

  const storedRun = await client.readRun(traceId);
  expect(storedRun.id).toEqual(traceId);
});

test("embedMany", async () => {
  const traceId = uuid();
  await embedMany({
    model: openai.embedding("text-embedding-3-small"),
    values: [
      "a peaceful meadow with wildflowers",
      "bustling city street at rush hour",
      "prague castle at sunset",
    ],
    experimental_telemetry: getTelemetrySettings(traceId),
  });

  await provider.forceFlush();
  await waitUntilRunFound(client, traceId, true);

  const storedRun = await client.readRun(traceId);
  expect(storedRun.id).toEqual(traceId);
});

afterAll(async () => {
  await provider.shutdown();
});
