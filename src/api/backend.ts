import type { Client, ClientClass, Order, Stage } from "../data";
import type { NewOrderInput } from "../store/AppStore";

type ApiClient = {
  id: number;
  name: string;
  phone: string;
  instagram?: string | null;
  logo_path?: string | null;
  created_at: string;
  updated_at: string;
};

type ApiCatalogItem = {
  id: number;
  display_name: string;
  size_cm?: number | null;
  product_type: string;
};

type ApiRevision = {
  id: number;
  revision_number: number;
};

type ApiOrder = {
  id: number;
  client: ApiClient;
  template: ApiCatalogItem;
  status: "draft" | "preview_sent" | "revision" | "approved" | "production" | "delivered";
  quantidade?: number | null;
  edit_data: Record<string, unknown>;
  updated_at: string;
  revisions?: ApiRevision[];
};

type BackendSnapshot = {
  orders: Order[];
  clients: Client[];
};

const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

const statusToStage: Record<ApiOrder["status"], Stage> = {
  draft: "Coleta de dados",
  preview_sent: "Preview enviado",
  revision: "Ajustes",
  approved: "Aprovado",
  production: "Impressão",
  delivered: "Impressão",
};

function normalizeBaseUrl(value: unknown) {
  if (typeof value !== "string" || !value.trim()) return "";
  return value.replace(/\/+$/, "");
}

function apiUrl(path: string) {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `API request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function formatDateLabel(value: string) {
  if (!value) return "sem data";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "sem data";

  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(0, Math.round(diffMs / 60000));
  if (diffMinutes < 2) return "agora";
  if (diffMinutes < 60) return `há ${diffMinutes} min`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `há ${diffHours} h`;
  const diffDays = Math.round(diffHours / 24);
  if (diffDays === 1) return "ontem";
  return `${diffDays} dias`;
}

function classifyClient(orderCount: number): ClientClass {
  if (orderCount >= 10) return "VIP";
  if (orderCount > 1) return "Recorrente";
  return "Primeiro pedido";
}

function boxSizeFrom(order: ApiOrder) {
  const fromEditData = order.edit_data.box_size;
  if (typeof fromEditData === "string" && fromEditData.trim()) return fromEditData;
  if (order.template.size_cm) return `${order.template.size_cm} cm`;
  return "—";
}

function cityFrom(order: ApiOrder) {
  const city = order.edit_data.city;
  return typeof city === "string" && city.trim() ? city : "Sem cidade";
}

function mapOrder(order: ApiOrder): Order {
  return {
    id: `PBX-${order.id}`,
    pizzaria: order.client.name,
    city: cityFrom(order),
    stage: statusToStage[order.status],
    updatedAt: formatDateLabel(order.updated_at),
    revisions: order.revisions?.length ?? 0,
    boxSize: boxSizeFrom(order),
  };
}

function mapClients(apiClients: ApiClient[], apiOrders: ApiOrder[]): Client[] {
  return apiClients.map((client) => {
    const clientOrders = apiOrders.filter((order) => order.client.id === client.id);
    const contact = clientOrders
      .map((order) => order.edit_data.contact_name)
      .find((value): value is string => typeof value === "string" && value.trim().length > 0);

    return {
      name: client.name,
      contact: contact || "Contato via WhatsApp",
      phone: client.phone,
      klass: classifyClient(clientOrders.length),
      orders: clientOrders.length,
      lastContact: formatDateLabel(client.updated_at),
    };
  });
}

function preferredTemplate(catalog: ApiCatalogItem[], input: NewOrderInput) {
  const size = Number(input.boxSize.replace(/\D/g, ""));
  return (
    catalog.find((item) => item.size_cm === size && item.product_type === "pizza") ??
    catalog.find((item) => item.product_type === "pizza") ??
    catalog[0]
  );
}

export const backendApi = {
  enabled: Boolean(API_BASE_URL),

  async loadSnapshot(): Promise<BackendSnapshot> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");

    const [apiClients, apiOrders] = await Promise.all([
      request<ApiClient[]>("/api/clients"),
      request<ApiOrder[]>("/api/orders"),
    ]);

    return {
      orders: apiOrders.map(mapOrder),
      clients: mapClients(apiClients, apiOrders),
    };
  },

  async createOrder(input: NewOrderInput): Promise<Order> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");

    const [client, catalog] = await Promise.all([
      request<ApiClient>("/api/clients", {
        method: "POST",
        body: JSON.stringify({
          name: input.pizzaria,
          phone: input.phone,
          instagram: input.instagram || null,
        }),
      }),
      request<ApiCatalogItem[]>("/api/catalog"),
    ]);

    const template = preferredTemplate(catalog, input);
    if (!template) {
      throw new Error("Nenhum template ativo encontrado no catalogo da API");
    }

    const order = await request<ApiOrder>("/api/orders", {
      method: "POST",
      body: JSON.stringify({
        client_id: client.id,
        template_id: template.id,
        edit_data: {
          business_name: input.pizzaria,
          city: input.city,
          contact_name: input.contact,
          phone: input.phone,
          instagram: input.instagram,
          required_text: input.requiredText,
          colors: input.colors,
          context: input.context,
          has_logo: input.hasLogo,
          has_reference: input.hasReference,
          box_size: input.boxSize,
        },
      }),
    });

    return mapOrder(order);
  },
};
