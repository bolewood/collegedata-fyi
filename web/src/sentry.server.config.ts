import * as Sentry from "@sentry/nextjs";
import { sentryInitOptions } from "@/lib/sentry";

Sentry.init(sentryInitOptions());
