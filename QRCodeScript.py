import pandas as pd

# Função de substituição de valores
def substituir_valores(valor):
    return 1.00 if valor >= 100 else valor * 0.01 if 51 < valor < 100 else 0.50

# Função para truncar valores para duas casas decimais
def truncar_valores(valor):
    return int(valor * 100) / 100.0

# Função para encontrar o próximo dia útil
def next_business_day(date):
    next_day = date + pd.Timedelta(days=1)
    while next_day.weekday() > 4:
        next_day += pd.Timedelta(days=1)
    return next_day

def business_date(date):
    next_day = date
    while next_day.weekday() > 4:
        next_day += pd.Timedelta(days=1)
    return next_day

def round_num(num):
    return round(num, 2)

def adjust_comparison_date(comparison_date, holidays):
    next_day = comparison_date 
    for holiday in holidays:
        if((next_day == holiday.date())):
            next_day += pd.Timedelta(days=1)
        elif(next_day == business_date(holiday.date() + pd.Timedelta(days=1))):
            next_day = business_date(next_day + pd.Timedelta(days=1))
    while next_day.weekday() > 4:
        next_day += pd.Timedelta(days=1)
    return next_day
 

# Função para mapear dias da semana para pares de comparação
def get_comparison_date(weekday):
    if weekday == 0 or weekday == 1:  # Segunda ou terça
        return 3  # Quinta-feira
    elif weekday == 2:  # Quarta-feira
        return 4  # Sexta-feira
    elif weekday == 3:  # Quinta-feira
        return 0  # Segunda-feira da semana seguinte
    elif weekday == 4:  # Sexta-feira
        return 1  # Terça-feira da semana seguinte
    return None

# Listar feriados (podem ser inputados pelo usuário)
holidays_input = input("Digite as datas de feriados no formato 'AAAA-MM-DD', separadas por vírgula: ")
holidays = pd.to_datetime(holidays_input.split(','))

# Ler CSV e converter a coluna 'DATA' para datetime
df = pd.read_csv("filial.csv", header=2, encoding='ISO8859-1', sep=';')
df['DATA'] = pd.to_datetime(df['DATA'], format='%d/%m/%y', errors='coerce')
df['DATA'] = df['DATA'].ffill()

# Remover coluna 'DOCTO.'
df.drop(columns=['DOCTO'], inplace=True)

# Filtrar transações PIX e TARIFA
df_pix = df[df['HISTÓRICO'].str.contains("PIX QR CODE DINAMIC REM:", na=False)].copy()
df_tarifa = df[df['HISTÓRICO'].str.contains("TARIFA BANCARIA LIQUIDACAO QRCODE PIX", na=False)].copy()

# Ajustar valores de crédito e débito
df_pix['CRÉDITO'] = df_pix['CRÉDITO'].str.replace('.', '').str.replace(',', '.').astype(float).apply(substituir_valores).apply(truncar_valores)
df_tarifa['CRÉDITO'] = df_tarifa['DÉBITO'].str.replace('.', '').str.replace(',', '.').astype(float).abs().apply(round_num)
df_tarifa.drop(columns=['DÉBITO'], inplace=True)
df_pix.drop(columns=['DÉBITO'], inplace=True)

# Inicializar DataFrame resultante
result_df = pd.DataFrame()

# Agrupar transações PIX por dia
pix_groups = df_pix.groupby(df_pix['DATA'].dt.date)
tarifa_groups = df_tarifa.groupby(df_tarifa['DATA'].dt.date)

combined_pix = pd.concat([group for date, group in pix_groups if date.weekday() in [0, 1]])
combined_pix['DATA'] = pd.to_datetime(combined_pix['DATA'])

monday = pd.DataFrame()

# Processar cada grupo de transações PIX
for pix_date, pix_group in pix_groups:
    pix_date = pd.to_datetime(pix_date).date()
    pix_weekday = pix_date.weekday()
    comparison_weekday = get_comparison_date(pix_weekday)

    if comparison_weekday is not None:
        if pix_weekday in [0, 1]:
            if pix_date not in combined_pix['DATA'].dt.date.values:
                print("a")
                continue

            if pix_weekday == 0:
                monday = combined_pix[combined_pix['DATA'].dt.date.values == pix_date]

            combined_group = pd.concat([monday, combined_pix[combined_pix['DATA'].dt.date.values == pix_date]]) if pix_weekday == 1 else pd.DataFrame()
        else:
            combined_group = pix_group

        if combined_group.empty or 'CRÉDITO' not in combined_group:
            continue

    # Encontrar a data de comparação
        comparison_date = pix_date + pd.Timedelta(days=(comparison_weekday - pix_weekday) if pix_weekday in [0, 1, 2] else (7 - pix_weekday + comparison_weekday))

        # Ajustar a data de comparação para o próximo dia útil se for um feriado
        comparison_date = adjust_comparison_date(comparison_date, holidays)
        

        # Filtrar transações TARIFA para a data de comparação
        if comparison_date in tarifa_groups.groups:
            tarifa_for_pix = tarifa_groups.get_group(comparison_date)
            total_tarifa = tarifa_for_pix['CRÉDITO'].sum()

            if total_tarifa != 0:
                result_df = pd.concat([result_df, combined_group, tarifa_for_pix])
                total_pix = combined_group['CRÉDITO'].sum()

                # Adicionar linhas de total
                total_pix_row = pd.Series({'DATA': '', 'HISTÓRICO': 'Total PIX QR CODE DINAMIC', 'CRÉDITO': total_pix})
                total_tarifa_row = pd.Series({'DATA': '', 'HISTÓRICO': 'Total TARIFA BANCARIA', 'CRÉDITO': total_tarifa})
                result_df = pd.concat([result_df, total_pix_row.to_frame().T, total_tarifa_row.to_frame().T], ignore_index=True)

# Remover colunas desnecessárias e resetar índice
result_df.drop(columns=['SALDO'], inplace=True, errors='ignore')
result_df.reset_index(drop=True, inplace=True)

# Salvar DataFrame resultante em um arquivo Excel
result_df.to_excel('mascaraTarifa.xlsx', index=False)
