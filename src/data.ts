import type { Tone } from "./components/ui/primitives";

/* Pipeline stages of a pizza-box art order (from scope: atendimento → aprovação) */
export const STAGES = [
  "Atendimento",
  "Coleta de dados",
  "Montagem por camadas",
  "Preview enviado",
  "Ajustes",
  "Aprovado",
  "Impressão",
] as const;
export type Stage = (typeof STAGES)[number];

export interface Order {
  id: string;
  pizzaria: string;
  city: string;
  stage: Stage;
  updatedAt: string;
  revisions: number;
  boxSize: string;
}

export const ORDERS: Order[] = [
  { id: "PBX-2418", pizzaria: "Forno di Napoli", city: "Campinas, SP", stage: "Preview enviado", updatedAt: "há 12 min", revisions: 2, boxSize: "35 cm" },
  { id: "PBX-2417", pizzaria: "Cantina do Zé", city: "Valinhos, SP", stage: "Ajustes", updatedAt: "há 40 min", revisions: 4, boxSize: "40 cm" },
  { id: "PBX-2415", pizzaria: "Pizza Prime", city: "Campinas, SP", stage: "Montagem por camadas", updatedAt: "há 1 h", revisions: 0, boxSize: "30 cm" },
  { id: "PBX-2414", pizzaria: "Bella Massa", city: "Hortolândia, SP", stage: "Aprovado", updatedAt: "há 2 h", revisions: 1, boxSize: "35 cm" },
  { id: "PBX-2411", pizzaria: "Dom Giuseppe", city: "Sumaré, SP", stage: "Coleta de dados", updatedAt: "há 3 h", revisions: 0, boxSize: "35 cm" },
  { id: "PBX-2409", pizzaria: "Redonda Pizzaria", city: "Paulínia, SP", stage: "Impressão", updatedAt: "ontem", revisions: 2, boxSize: "40 cm" },
  { id: "PBX-2405", pizzaria: "Nonna Rosa", city: "Campinas, SP", stage: "Atendimento", updatedAt: "ontem", revisions: 0, boxSize: "—" },
];

export const stageTone: Record<Stage, Tone> = {
  Atendimento: "neutral",
  "Coleta de dados": "neutral",
  "Montagem por camadas": "cheese",
  "Preview enviado": "sauce",
  Ajustes: "cheese",
  Aprovado: "basil",
  Impressão: "ink",
};

/* CRM classifications from scope 2.3 */
export type ClientClass =
  | "VIP"
  | "Recorrente"
  | "Primeiro pedido"
  | "Abandono por preço"
  | "Abandono no processo"
  | "Reativado";

export const classTone: Record<ClientClass, Tone> = {
  VIP: "cheese",
  Recorrente: "basil",
  "Primeiro pedido": "sauce",
  "Abandono por preço": "neutral",
  "Abandono no processo": "neutral",
  Reativado: "sauce",
};

export interface Client {
  name: string;
  contact: string;
  phone: string;
  klass: ClientClass;
  orders: number;
  lastContact: string;
}

export const CLIENTS: Client[] = [
  { name: "Forno di Napoli", contact: "Marina Belluci", phone: "+55 19 99812-4471", klass: "VIP", orders: 14, lastContact: "Hoje" },
  { name: "Cantina do Zé", contact: "José Andrade", phone: "+55 19 99640-1120", klass: "Recorrente", orders: 6, lastContact: "Hoje" },
  { name: "Pizza Prime", contact: "Rafael Nunes", phone: "+55 19 99155-8830", klass: "Primeiro pedido", orders: 1, lastContact: "Ontem" },
  { name: "Bella Massa", contact: "Cláudia Reis", phone: "+55 19 99730-2214", klass: "Recorrente", orders: 8, lastContact: "Ontem" },
  { name: "Dom Giuseppe", contact: "Antônio Salle", phone: "+55 19 99001-7788", klass: "Reativado", orders: 3, lastContact: "2 dias" },
  { name: "Trattoria Sole", contact: "Paula Menezes", phone: "+55 19 99420-6650", klass: "Abandono por preço", orders: 0, lastContact: "5 dias" },
  { name: "Pizzaria Central", contact: "Bruno Faria", phone: "+55 19 99388-9042", klass: "Abandono no processo", orders: 0, lastContact: "8 dias" },
];

/* PSD storage files (scope 2.6) */
export interface PsdFile {
  name: string;
  client: string;
  size: number; // GB
  created: string;
  status: "Aprovado" | "Em ajuste" | "Arquivado";
  editable: boolean;
}
export const PSD_FILES: PsdFile[] = [
  { name: "fornodinapoli_35cm_final.psd", client: "Forno di Napoli", size: 1.8, created: "24 ago 2026", status: "Aprovado", editable: true },
  { name: "cantinadoze_40cm_v4.psd", client: "Cantina do Zé", size: 2.3, created: "24 ago 2026", status: "Em ajuste", editable: true },
  { name: "bellamassa_35cm_final.psd", client: "Bella Massa", size: 1.6, created: "23 ago 2026", status: "Aprovado", editable: true },
  { name: "redonda_40cm_final.psd", client: "Redonda Pizzaria", size: 2.1, created: "22 ago 2026", status: "Aprovado", editable: true },
  { name: "domgiuseppe_35cm_v1.psd", client: "Dom Giuseppe", size: 1.4, created: "21 ago 2026", status: "Em ajuste", editable: true },
  { name: "nonnarosa_30cm_2025.psd", client: "Nonna Rosa", size: 1.2, created: "12 dez 2025", status: "Arquivado", editable: true },
];

/* weekly render throughput for the chart */
export const WEEK = [
  { day: "S", value: 34 },
  { day: "T", value: 58 },
  { day: "Q", value: 46 },
  { day: "Q", value: 72 },
  { day: "S", value: 61 },
  { day: "S", value: 28 },
  { day: "D", value: 12 },
];

/* layer stack from scope 2.2 */
export const LAYERS = [
  "Fundo / Base",
  "Faca de corte",
  "Grafismos e bordas",
  "Ícones e ilustrações",
  "Logo / Marca",
  "Textos principais",
  "Informações de contato",
  "Selos e badges",
  "Marca d'água",
];
