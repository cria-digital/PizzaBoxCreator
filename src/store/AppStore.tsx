import {
  createContext,
  useEffect,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { backendApi, type ClientInput } from "../api/backend";
import {
  CLIENTS,
  ORDERS,
  STAGES,
  type Client,
  type ClientClass,
  type Order,
  type Stage,
} from "../data";

type User = {
  id: string;
  name: string;
  email: string;
  role: string;
};

export type NewOrderInput = {
  pizzaria: string;
  city: string;
  phone: string;
  contact: string;
  boxSize: string;
  instagram?: string;
  requiredText?: string;
  colors: string[];
  context?: string;
  hasLogo: boolean;
  hasReference: boolean;
};

export type ClientFormInput = ClientInput;

type AppStoreValue = {
  user: User | null;
  orders: Order[];
  clients: Client[];
  backendEnabled: boolean;
  authLoading: boolean;
  loadingData: boolean;
  dataError: string;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  createClient: (input: ClientFormInput) => Promise<Client>;
  updateClient: (client: Client, input: ClientFormInput) => Promise<Client>;
  deleteClient: (client: Client) => Promise<void>;
  createOrder: (input: NewOrderInput) => Promise<Order>;
  updateOrderStage: (orderId: string, stage: Stage) => void;
  reloadData: () => Promise<void>;
};

const DATA_KEY = "pizza-box-creator:data:v1";

const AppStoreContext = createContext<AppStoreValue | null>(null);

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson<T>(key: string, value: T) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

function nextOrderId(orders: Order[]) {
  const max = orders.reduce((highest, order) => {
    const numeric = Number(order.id.replace(/\D/g, ""));
    return Number.isFinite(numeric) ? Math.max(highest, numeric) : highest;
  }, 2400);
  return `PBX-${max + 1}`;
}

function classifyClient(existing?: Client): ClientClass {
  if (!existing) return "Primeiro pedido";
  if (existing.klass === "VIP") return "VIP";
  return existing.orders >= 5 ? "Recorrente" : existing.klass;
}

function nextClientId(clients: Client[]) {
  return clients.reduce((max, client) => Math.max(max, client.id ?? 0), 0) + 1;
}

function normalizePhone(value: string) {
  return value.replace(/\D/g, "");
}

function normalizeInstagram(value?: string) {
  const clean = (value || "").trim();
  if (!clean) return "";
  return clean.startsWith("@") ? clean : `@${clean}`;
}

type StoredData = {
  orders: Order[];
  clients: Client[];
};

export function AppStoreProvider({ children }: { children: ReactNode }) {
  const initialData = useMemo(
    () => readJson<StoredData>(DATA_KEY, { orders: ORDERS, clients: CLIENTS }),
    [],
  );

  const [user, setUser] = useState<User | null>(null);
  const [orders, setOrders] = useState<Order[]>(initialData.orders);
  const [clients, setClients] = useState<Client[]>(initialData.clients);
  const [authLoading, setAuthLoading] = useState(backendApi.enabled);
  const [loadingData, setLoadingData] = useState(false);
  const [dataError, setDataError] = useState("");

  function persist(nextOrders: Order[], nextClients: Client[]) {
    if (backendApi.enabled) return;
    writeJson(DATA_KEY, { orders: nextOrders, clients: nextClients });
  }

  async function reloadData() {
    if (!backendApi.enabled || !user) return;

    setLoadingData(true);
    setDataError("");
    try {
      const snapshot = await backendApi.loadSnapshot();
      setOrders(snapshot.orders);
      setClients(snapshot.clients);
    } catch (error) {
      setDataError(error instanceof Error ? error.message : "Falha ao carregar banco");
    } finally {
      setLoadingData(false);
    }
  }

  useEffect(() => {
    if (!backendApi.enabled) {
      setAuthLoading(false);
      return;
    }

    let active = true;
    backendApi
      .currentUser()
      .then((nextUser) => {
        if (active) setUser(nextUser);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (user) {
      void reloadData();
    } else {
      setLoadingData(false);
    }
  }, [user]);

  async function login(username: string, password: string) {
    if (!backendApi.enabled) {
      setDataError("VITE_API_BASE_URL nao configurada");
      return false;
    }

    try {
      const nextUser = await backendApi.login(username, password);
      setUser(nextUser);
      return true;
    } catch (error) {
      setDataError(error instanceof Error ? error.message : "Falha ao entrar");
      return false;
    }
  }

  async function logout() {
    await backendApi.logout().catch(() => undefined);
    setUser(null);
  }

  async function createOrder(input: NewOrderInput) {
    if (backendApi.enabled) {
      const order = await backendApi.createOrder(input);
      await reloadData();
      return order;
    }

    const existingClient = clients.find(
      (client) => client.name.toLowerCase() === input.pizzaria.trim().toLowerCase(),
    );
    const order: Order = {
      id: nextOrderId(orders),
      pizzaria: input.pizzaria.trim(),
      city: input.city.trim() || "Sem cidade",
      stage: "Coleta de dados",
      updatedAt: "agora",
      revisions: 0,
      boxSize: input.boxSize,
    };

    const nextClients = existingClient
      ? clients.map((client) =>
          client.name === existingClient.name
            ? {
                ...client,
                phone: input.phone.trim() || client.phone,
                contact: input.contact.trim() || client.contact,
                klass: classifyClient(client),
                orders: client.orders + 1,
                lastContact: "Hoje",
              }
            : client,
        )
      : [
          {
            name: order.pizzaria,
            contact: input.contact.trim() || "Contato via WhatsApp",
            phone: input.phone.trim() || "Não informado",
            klass: classifyClient(),
            orders: 1,
            lastContact: "Hoje",
          },
          ...clients,
        ];

    const nextOrders = [order, ...orders];
    setOrders(nextOrders);
    setClients(nextClients);
    persist(nextOrders, nextClients);
    return order;
  }

  async function createClient(input: ClientFormInput) {
    if (backendApi.enabled) {
      const client = await backendApi.createClient(input);
      await reloadData();
      return client;
    }

    const phone = normalizePhone(input.phone);
    const existing = clients.find((client) => normalizePhone(client.phone) === phone);
    if (existing) {
      throw new Error("Ja existe cliente com esse telefone");
    }

    const nextClient: Client = {
      id: nextClientId(clients),
      name: input.name.trim(),
      contact: "Contato via WhatsApp",
      phone,
      instagram: normalizeInstagram(input.instagram),
      logoPath: input.logoPath || null,
      klass: "Primeiro pedido",
      orders: 0,
      lastContact: "Hoje",
    };
    const nextClients = [nextClient, ...clients];
    setClients(nextClients);
    persist(orders, nextClients);
    return nextClient;
  }

  async function updateClient(client: Client, input: ClientFormInput) {
    if (backendApi.enabled) {
      if (!client.id) throw new Error("Cliente sem ID de backend");
      const updated = await backendApi.updateClient(client.id, input);
      await reloadData();
      return updated;
    }

    const phone = normalizePhone(input.phone);
    const duplicate = clients.find(
      (item) => item !== client && normalizePhone(item.phone) === phone,
    );
    if (duplicate) {
      throw new Error("Ja existe cliente com esse telefone");
    }

    let updatedClient: Client = client;
    const nextClients = clients.map((item) => {
      if (item !== client) return item;
      updatedClient = {
        ...item,
        name: input.name.trim(),
        phone,
        instagram: normalizeInstagram(input.instagram),
        logoPath: input.logoPath || item.logoPath || null,
        lastContact: "Hoje",
      };
      return updatedClient;
    });
    setClients(nextClients);
    persist(orders, nextClients);
    return updatedClient;
  }

  async function deleteClient(client: Client) {
    if (client.orders > 0) {
      throw new Error("Cliente possui pedidos e nao pode ser excluido");
    }

    if (backendApi.enabled) {
      if (!client.id) throw new Error("Cliente sem ID de backend");
      await backendApi.deleteClient(client.id);
      await reloadData();
      return;
    }

    const nextClients = clients.filter((item) => item !== client);
    setClients(nextClients);
    persist(orders, nextClients);
  }

  function updateOrderStage(orderId: string, stage: Stage) {
    if (!STAGES.includes(stage)) return;
    setOrders((current) => {
      const nextOrders = current.map((order) =>
        order.id === orderId ? { ...order, stage, updatedAt: "agora" } : order,
      );
      persist(nextOrders, clients);
      return nextOrders;
    });
  }

  const value: AppStoreValue = {
    user,
    orders,
    clients,
    backendEnabled: backendApi.enabled,
    authLoading,
    loadingData,
    dataError,
    login,
    logout,
    createClient,
    updateClient,
    deleteClient,
    createOrder,
    updateOrderStage,
    reloadData,
  };

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>;
}

export function useAppStore() {
  const store = useContext(AppStoreContext);
  if (!store) {
    throw new Error("useAppStore must be used inside AppStoreProvider");
  }
  return store;
}
