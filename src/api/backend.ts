import type { AuditEntry, CatalogItem, Client, ClientClass, Order, OrderFile, Stage } from "../data";
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

export type ClientInput = {
  name: string;
  phone: string;
  instagram?: string;
  logoPath?: string | null;
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
  preview_url?: string | null;
  cmyk_url?: string | null;
  package_url?: string | null;
  created_at: string;
  updated_at: string;
  revisions?: ApiRevision[];
};

type ApiOrderFile = {
  kind: string;
  filename: string;
  download_url: string;
  exists: boolean;
};

type ApiAuditEntry = {
  id: number;
  order_id?: number | null;
  username: string;
  action: string;
  details?: Record<string, unknown> | null;
  created_at: string;
};

type BackendSnapshot = {
  orders: Order[];
  clients: Client[];
};

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: string;
};

export type CrmClassification = "new" | "active" | "vip" | "at_risk" | "abandoned" | "inactive";
export type CrmStage = "lead" | "qualified" | "order_created" | "preview_sent" | "revision" | "approved" | "production" | "delivered";

export type CrmContact = {
  id: number;
  client_id: number;
  classification: CrmClassification;
  lifecycle_stage: CrmStage;
  score: number;
  last_contact_at?: string | null;
  classification_reason?: string | null;
  client: ApiClient;
};

export type CrmMetrics = {
  contacts_total: number;
  new_contacts: number;
  by_classification: Record<CrmClassification, number>;
  by_stage: Record<CrmStage, number>;
  stage_clients: Record<CrmStage, number>;
  conversions: Record<"lead_to_order" | "order_to_preview" | "preview_to_approved" | "approved_to_delivered", number | null>;
  abandoned_count: number;
  abandoned_rate: number | null;
  vip_count: number;
  reengagement: Record<string, number>;
};

export type CrmReengagement = {
  id: number;
  client_id: number;
  order_id?: number | null;
  client_name: string;
  client_phone: string;
  reason: string;
  status: "pending" | "sent" | "skipped" | "failed";
  scheduled_for?: string | null;
};

type AuthResponse = {
  user: AuthUser;
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

const stageToStatus: Record<Stage, ApiOrder["status"]> = {
  Atendimento: "draft",
  "Coleta de dados": "draft",
  "Montagem por camadas": "revision",
  "Preview enviado": "preview_sent",
  Ajustes: "revision",
  Aprovado: "approved",
  Impressão: "production",
};

function normalizeBaseUrl(value: unknown) {
  if (typeof value !== "string" || !value.trim()) return "";
  return value.replace(/\/+$/, "");
}

function apiUrl(path: string) {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(apiUrl(path), {
    ...init,
    credentials: "include",
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let message = text;
    try {
      const data = JSON.parse(text) as { detail?: string };
      message = data.detail || message;
    } catch {
      // Keep the raw response body when it is not JSON.
    }
    throw new Error(message || `API request failed with ${response.status}`);
  }

  if (response.status === 204) return undefined as T;
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
    backendId: order.id,
    pizzaria: order.client.name,
    city: cityFrom(order),
    stage: statusToStage[order.status],
    updatedAt: formatDateLabel(order.updated_at),
    revisions: order.revisions?.length ?? 0,
    boxSize: boxSizeFrom(order),
    quantity: order.quantidade ?? null,
    templateName: order.template.display_name,
    previewUrl: order.preview_url ?? null,
    productionUrl: order.cmyk_url ?? null,
    packageUrl: order.package_url ?? null,
  };
}

function mapClients(apiClients: ApiClient[], apiOrders: ApiOrder[]): Client[] {
  return apiClients.map((client) => {
    const clientOrders = apiOrders.filter((order) => order.client.id === client.id);
    const contact = clientOrders
      .map((order) => order.edit_data.contact_name)
      .find((value): value is string => typeof value === "string" && value.trim().length > 0);

    return {
      id: client.id,
      name: client.name,
      contact: contact || "Contato via WhatsApp",
      phone: client.phone,
      instagram: client.instagram || "",
      logoPath: client.logo_path || null,
      klass: classifyClient(clientOrders.length),
      orders: clientOrders.length,
      lastContact: formatDateLabel(client.updated_at),
    };
  });
}

function preferredTemplate(catalog: ApiCatalogItem[], input: NewOrderInput) {
  if (input.templateId) {
    const selected = catalog.find((item) => item.id === input.templateId);
    if (selected) return selected;
  }
  const size = Number(input.boxSize.replace(/\D/g, ""));
  return (
    catalog.find((item) => item.size_cm === size && item.product_type === "pizza") ??
    catalog.find((item) => item.product_type === "pizza") ??
    catalog[0]
  );
}

function mapCatalog(item: ApiCatalogItem): CatalogItem {
  return {
    id: item.id,
    displayName: item.display_name,
    sizeCm: item.size_cm ?? null,
    productType: item.product_type,
  };
}

function mapOrderFile(file: ApiOrderFile): OrderFile {
  return {
    kind: file.kind,
    filename: file.filename,
    downloadUrl: apiUrl(file.download_url),
    exists: file.exists,
  };
}

function mapAudit(entry: ApiAuditEntry): AuditEntry {
  return {
    id: entry.id,
    orderId: entry.order_id ?? null,
    username: entry.username,
    action: entry.action,
    details: entry.details ?? null,
    createdAt: formatDateLabel(entry.created_at),
  };
}

function backendIdFromOrderId(orderId: string | number) {
  if (typeof orderId === "number") return orderId;
  const id = Number(orderId.replace(/\D/g, ""));
  if (!Number.isFinite(id)) throw new Error("Pedido sem ID de backend");
  return id;
}

async function uploadOrderFile(
  file: File,
  purpose: "logo" | "reference",
  ids: { clientId?: number; orderId?: number },
) {
  const form = new FormData();
  form.append("file", file);
  form.append("purpose", purpose);
  if (ids.clientId) form.append("client_id", String(ids.clientId));
  if (ids.orderId) form.append("order_id", String(ids.orderId));
  return request<{ asset_path: string }>("/api/files", {
    method: "POST",
    body: form,
  });
}

export const backendApi = {
  enabled: Boolean(API_BASE_URL),

  async login(username: string, password: string): Promise<AuthUser> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");

    const response = await request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    return response.user;
  },

  async currentUser(): Promise<AuthUser> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");

    const response = await request<AuthResponse>("/api/auth/me");
    return response.user;
  },

  async logout(): Promise<void> {
    if (!API_BASE_URL) return;
    await request<void>("/api/auth/logout", { method: "POST" });
  },

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

  async loadCatalog(): Promise<CatalogItem[]> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");
    const catalog = await request<ApiCatalogItem[]>("/api/catalog");
    return catalog.map(mapCatalog);
  },

  async createOrder(input: NewOrderInput): Promise<Order> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");

    const client = await request<ApiClient>("/api/clients", {
      method: "POST",
      body: JSON.stringify({
        name: input.pizzaria,
        phone: input.phone,
        instagram: input.instagram || null,
      }),
    });

    const logoUpload = input.logoFile
      ? await uploadOrderFile(input.logoFile, "logo", { clientId: client.id })
      : null;
    const catalog = await request<ApiCatalogItem[]>("/api/catalog");

    const template = preferredTemplate(catalog, input);
    if (!template) {
      throw new Error("Nenhum template ativo encontrado no catalogo da API");
    }

    const order = await request<ApiOrder>("/api/orders", {
      method: "POST",
      body: JSON.stringify({
        client_id: client.id,
        template_id: template.id,
        quantidade: input.quantity || null,
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
          logo_path: logoUpload?.asset_path,
        },
      }),
    });

    if (input.referenceFiles.length) {
      await Promise.all(
        input.referenceFiles.map((file) =>
          uploadOrderFile(file, "reference", { orderId: order.id }),
        ),
      );
      const withFiles = await request<ApiOrder>(`/api/orders/${order.id}`);
      return mapOrder(withFiles);
    }

    return mapOrder(order);
  },

  async updateOrderStage(orderId: string | number, stage: Stage): Promise<Order> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");
    const id = backendIdFromOrderId(orderId);
    const order = await request<ApiOrder>(`/api/orders/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: stageToStatus[stage] }),
    });
    return mapOrder(order);
  },

  async uploadOrderAsset(orderId: string | number, file: File, purpose: "logo" | "reference"): Promise<void> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");
    const id = backendIdFromOrderId(orderId);
    await uploadOrderFile(file, purpose, { orderId: id });
  },

  async listOrderFiles(orderId: string | number): Promise<OrderFile[]> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");
    const id = backendIdFromOrderId(orderId);
    const files = await request<ApiOrderFile[]>(`/api/files/orders/${id}`);
    return files.map(mapOrderFile);
  },

  async listOrderAudit(orderId: string | number): Promise<AuditEntry[]> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");
    const id = backendIdFromOrderId(orderId);
    const entries = await request<ApiAuditEntry[]>(`/api/orders/${id}/audit`);
    return entries.map(mapAudit);
  },

  async createClient(input: ClientInput): Promise<Client> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");

    const client = await request<ApiClient>("/api/clients", {
      method: "POST",
      body: JSON.stringify({
        name: input.name,
        phone: input.phone,
        instagram: input.instagram || null,
        logo_path: input.logoPath || null,
      }),
    });

    return mapClients([client], [])[0];
  },

  async updateClient(clientId: number, input: Partial<ClientInput>): Promise<Client> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");

    const body: Record<string, string | null> = {};
    if (input.name !== undefined) body.name = input.name;
    if (input.phone !== undefined) body.phone = input.phone;
    if (input.instagram !== undefined) body.instagram = input.instagram || null;
    if (input.logoPath !== undefined) body.logo_path = input.logoPath || null;

    const client = await request<ApiClient>(`/api/clients/${clientId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });

    return mapClients([client], [])[0];
  },

  async deleteClient(clientId: number): Promise<void> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");
    await request<void>(`/api/clients/${clientId}`, { method: "DELETE" });
  },

  async loadCrm(): Promise<{ contacts: CrmContact[]; metrics: CrmMetrics; tasks: CrmReengagement[] }> {
    if (!API_BASE_URL) throw new Error("VITE_API_BASE_URL is not configured");
    const [contacts, metrics, tasks] = await Promise.all([
      request<CrmContact[]>("/api/crm/contacts"),
      request<CrmMetrics>("/api/crm/metrics"),
      request<CrmReengagement[]>("/api/crm/reengagement?status=pending"),
    ]);
    return { contacts, metrics, tasks };
  },

  async reclassifyCrm(): Promise<void> {
    await request("/api/crm/reclassify", { method: "POST" });
  },

  async markReengagementSent(taskId: number): Promise<void> {
    await request(`/api/crm/reengagement/${taskId}/send`, { method: "POST" });
  },

  async skipReengagement(taskId: number): Promise<void> {
    await request(`/api/crm/reengagement/${taskId}/skip`, {
      method: "POST",
      body: JSON.stringify({ note: "Ignorado pelo operador" }),
    });
  },
};
