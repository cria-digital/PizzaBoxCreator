import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
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

type Account = User & {
  password: string;
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

type AppStoreValue = {
  user: User | null;
  orders: Order[];
  clients: Client[];
  login: (email: string, password: string) => boolean;
  logout: () => void;
  createOrder: (input: NewOrderInput) => Order;
  updateOrderStage: (orderId: string, stage: Stage) => void;
};

const DATA_KEY = "pizza-box-creator:data:v1";
const SESSION_KEY = "pizza-box-creator:session:v1";

const ACCOUNTS: Account[] = [
  {
    id: "usr_designer",
    name: "Marina Costa",
    email: "designer@pizzabox.com.br",
    password: "design123",
    role: "Designer",
  },
  {
    id: "usr_admin",
    name: "Admin Pizza Box",
    email: "admin@pizzabox.com.br",
    password: "admin123",
    role: "Administrador",
  },
];

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

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
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

type StoredData = {
  orders: Order[];
  clients: Client[];
};

export function AppStoreProvider({ children }: { children: ReactNode }) {
  const initialData = useMemo(
    () => readJson<StoredData>(DATA_KEY, { orders: ORDERS, clients: CLIENTS }),
    [],
  );
  const initialUser = useMemo(() => {
    const email = readJson<string | null>(SESSION_KEY, null);
    const account = email ? ACCOUNTS.find((item) => item.email === email) : undefined;
    return account
      ? {
          id: account.id,
          name: account.name,
          email: account.email,
          role: account.role,
        }
      : null;
  }, []);

  const [user, setUser] = useState<User | null>(initialUser);
  const [orders, setOrders] = useState<Order[]>(initialData.orders);
  const [clients, setClients] = useState<Client[]>(initialData.clients);

  function persist(nextOrders: Order[], nextClients: Client[]) {
    writeJson(DATA_KEY, { orders: nextOrders, clients: nextClients });
  }

  function login(email: string, password: string) {
    const account = ACCOUNTS.find(
      (item) => item.email === normalizeEmail(email) && item.password === password,
    );
    if (!account) return false;

    const nextUser = {
      id: account.id,
      name: account.name,
      email: account.email,
      role: account.role,
    };
    setUser(nextUser);
    writeJson(SESSION_KEY, account.email);
    return true;
  }

  function logout() {
    setUser(null);
    window.localStorage.removeItem(SESSION_KEY);
  }

  function createOrder(input: NewOrderInput) {
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
    login,
    logout,
    createOrder,
    updateOrderStage,
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
