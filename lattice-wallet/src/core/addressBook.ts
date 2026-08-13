// Local address book — contacts stored on-device only. Sending to a saved contact means
// you verify the address once, then trust the label; this reduces address-swap/paste
// attacks (a common way funds are stolen).
import { loadJson, saveJson } from './storage';

export interface Contact {
  id: string;
  name: string;
  address: string;
  chainId: string; // which chain this address is for
}

const KEY = 'lattice.contacts.v1';

export async function loadContacts(): Promise<Contact[]> {
  return loadJson<Contact[]>(KEY, []);
}

export async function addContact(c: Omit<Contact, 'id'>): Promise<Contact> {
  const list = await loadContacts();
  // Derive a stable id without Date.now/Math.random (unavailable in some contexts):
  const id = `${c.chainId}:${c.address.toLowerCase()}`;
  const contact: Contact = { ...c, id };
  const next = [contact, ...list.filter((x) => x.id !== id)];
  await saveJson(KEY, next);
  return contact;
}

export async function removeContact(id: string): Promise<void> {
  const list = await loadContacts();
  await saveJson(KEY, list.filter((c) => c.id !== id));
}

export async function contactsForChain(chainId: string): Promise<Contact[]> {
  return (await loadContacts()).filter((c) => c.chainId === chainId);
}
