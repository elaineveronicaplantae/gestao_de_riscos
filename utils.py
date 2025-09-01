import os
import json
import pandas as pd
from io import BytesIO
from flask import Response
from xhtml2pdf import pisa
import smtplib
from email.mime.text import MIMEText

def salvar_em_excel(dados):
    caminho = "respostas_preenchidas.xlsx"

    descricoes_alertas = {
        "hist1_alerta": "Cliente com Histórico de Endividamento elevado no setor agrícola",
        "hist2_alerta": "Cliente já citado em alertas anteriores",
        "mov1_alerta": "Movimentação mensal 30% acima da capacidade financeira",
        "mov2_alerta": "Entradas com origem incompatível",
        "mov3_alerta": "Liquidações antecipadas frequentemente, ≥ a 2 contratos liquidados antecipadamente",
        "mov4_alerta": "Entrada/saída concentrada em poucos dias",
        "mov5_alerta": "Transferência entre empresas do mesmo grupo sem justificativa",
        "perfil1_alerta": "Perfil de risco divergente do histórico de crédito",
        "perfil2_alerta": "Mudança repentina de endereço ou estrutura",
        "perfil3_alerta": "Uso de laranjas para movimentar recursos",
        "perfil4_alerta": "Recusa em fornecer informações cadastrais",
        "perfil5_alerta": "Atividade sensível (Econômica/Profissional) ou Praça de Fronteira",
        "cad1_alerta": "Cadastrado com documentos inválidos ou vencidos",
        "cad2_alerta": "CPF/CNPJ com pendências legais graves",
        "cad4_alerta": "Contratos ou documentos com rasuras",
        "cad5_alerta": "Incompatibilidade entre dados fornecidos e fontes oficiais",
        "cad6_alerta": "Cadastrado por colaborador sem alçada"
    }

    motivos = []
    for campo, descricao in descricoes_alertas.items():
        if dados.get(campo, "").strip().lower() == "sim":
            motivos.append(descricao)

    pareceres = []
    if dados.get("coaf", "").strip().lower() == "sim":
        pareceres.append("Comunicar ao COAF")
    if dados.get("arquivar_alerta", "").strip().lower() == "sim":
        pareceres.append("Arquivar o alerta")
    if dados.get("bloquear_cadastro", "").strip().lower() == "sim":
        pareceres.append("Bloquear o Cadastro")
    if dados.get("solicitar_atualizacao", "").strip().lower() == "sim":
        pareceres.append("Solicitar atualização cadastral")
    if dados.get("outros_parecer", "").strip().lower() == "sim":
        pareceres.append("Outros")

    df_novo = pd.DataFrame([{
        "Nº Contrato/Operação": dados.get("contrato", ""),
        "Data Pagamento Contrato/Operação": dados.get("data_pagamento", ""),
        "Data de Preenchimento": dados.get("data_preenchimento", ""),
        "Cliente": dados.get("cliente_nome", ""),
        "Gestor de Relacionamento": dados.get("nome_gestor_relacionamento", ""),
        "Valor Contrato/Operação": dados.get("valor", ""),
        "Motivo": "; ".join(motivos),
        "Parecer Final": "; ".join(pareceres),
        "Responsável pelo Apontamento": dados.get("responsavel_apontamento", ""),
        "Responsável pelo Preenchimento": dados.get("responsavel_preenchimento", ""),
        "4. Comentários Adicionais - Apontamento": dados.get("comentario_adicional_apontamento", ""),
        "5. Pareceres Adicionais - Resposta": dados.get("pareceres_adicionais_resposta", ""),
        "6. Comentários Adicionais – Área de Crédito": dados.get("comentarios_credito", ""),
        "8. Parecer final - Diretoria Responsável por PLD/FT": dados.get("parecer_diretoria", "")
    }])

    if os.path.exists(caminho):
        df_existente = pd.read_excel(caminho)
        df_existente = df_existente[df_existente["Nº Contrato/Operação"] != dados.get("contrato", "")]
        df_atualizado = pd.concat([df_existente, df_novo], ignore_index=True)
    else:
        df_atualizado = df_novo

    df_atualizado.to_excel(caminho, index=False)

def enviar_email(destinatario, email_usuario, contrato, servidor_smtp="smtp.gmail.com", porta=587):
    remetente = "formularios@plantaeagrocredito.com.br"
    senha = "tmoa mjvm iwrj gmfd"

    assunto = "Formulário GR10 A07 - Monitoramento de PLD"
    link = f"http://85.25.172.144:5000/formulario?contrato={contrato}"
    corpo = (
        f"{destinatario},\n\n"
        f"Segue o link para preenchimento do formulário GR10 A07 - Monitoramento de PLD.\n"
        f"{link}\n\n"
        f"Lembre-se que o prazo para resposta é de 3 dias úteis.\n\n"
        f"Em caso de dúvidas, acione o time de Compliance.\n\n"
        f"Atenciosamente,\n{email_usuario}"
    )

    msg = MIMEText(corpo, _charset="utf-8")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario

    with smtplib.SMTP(servidor_smtp, porta) as server:
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, [destinatario], msg.as_string())
