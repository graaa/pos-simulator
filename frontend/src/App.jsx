import React, { useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://64.227.83.209:8001'

export default function App(){
  const [items, setItems] = useState([
    { name: 'Beer', qty: 1, price: 2500 },
  ])
  const [table, setTable] = useState('Mesa 1')
  const [order, setOrder] = useState(null)
  const [tip, setTip] = useState(0)
  const [txn, setTxn] = useState(null)

  const subtotal = items.reduce((s,i)=> s + i.qty*i.price, 0)

  async function createOrder(){
    const r = await fetch(`${API}/orders`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ table, items })
    })
    const data = await r.json()
    setOrder(data)
    setTxn(null)
  }

  async function charge(){
    if(!order) return
    const r = await fetch(`${API}/payments/charge`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ order_id: order.id, tip: Number(tip)||0 })
    })
    const data = await r.json()
    setTxn(data)
  }

  function updateItem(idx, field, value){
    const copy = items.slice()
    copy[idx] = { ...copy[idx], [field]: field==='name'? value : Number(value) }
    setItems(copy)
  }

  function addItem(){
    setItems([...items, { name:'Item', qty:1, price:1000 }])
  }

  return (
    <div style={{maxWidth: 720, margin: '40px auto', fontFamily: 'system-ui, sans-serif'}}>
      <h1>CaamañoPOS Demo</h1>

      <section style={{padding:12, border:'1px solid #ddd', borderRadius:8, marginBottom:16}}>
        <h3>Order</h3>
        <label>Table:&nbsp;
          <input value={table} onChange={e=>setTable(e.target.value)} />
        </label>
        <div style={{marginTop:8}}>
          {items.map((it,idx)=> (
            <div key={idx} style={{display:'grid', gridTemplateColumns:'2fr 1fr 1fr', gap:8, marginBottom:6}}>
              <input value={it.name} onChange={e=>updateItem(idx,'name', e.target.value)} />
              <input type="number" value={it.qty} onChange={e=>updateItem(idx,'qty', e.target.value)} />
              <input type="number" value={it.price} onChange={e=>updateItem(idx,'price', e.target.value)} />
            </div>
          ))}
          <button onClick={addItem}>+ Add item</button>
        </div>
        <div style={{marginTop:8}}>Subtotal: ₡{subtotal.toFixed(2)}</div>
        <button style={{marginTop:8}} onClick={createOrder}>Create Order</button>
      </section>

      {order && (
        <section style={{padding:12, border:'1px solid #ddd', borderRadius:8, marginBottom:16}}>
          <h3>Payment</h3>
          <div>Order #{order.id} — Total now (subtotal + tip)</div>
          <label>Tip: ₡ <input type="number" value={tip} onChange={e=>setTip(e.target.value)} /></label>
          <div style={{marginTop:8}}>
            <button onClick={charge}>Charge on terminal</button>
          </div>
        </section>
      )}

      {txn && (
        <section style={{padding:12, border:'1px solid #4caf50', borderRadius:8}}>
          <h3>Result</h3>
          <pre>{JSON.stringify(txn, null, 2)}</pre>
          <p style={{fontSize:12, color:'#555'}}>Note: Only status/auth_code/masked_card/terminal_ref are returned — no PAN/CVV handled by POS.</p>
        </section>
      )}
    </div>
  )
}
