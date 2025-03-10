from app.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import psycopg2
import sqlalchemy
import dash
import dash_table
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from app.models_bd import Titres, Positions, Contrats, Base
import numpy as np
from datetime import datetime, timedelta
from app.objects_plotly import home, open_ticker, analyse_duree, analyse_titre, PlotContrat
#import pandas_datareader.data as web

fig = make_subplots(specs=[[{"secondary_y": True}]])


#connection avec base de données
engine = create_engine(Config.DATABASE_URI)

#Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session= Session()

#mes_position = pd.read_sql('SELECT * FROM positions', con=engine)
mes_position = pd.read_sql('positions', engine)
objet_position = session.query(Positions).filter_by(statut='close').all()
session.close()


mes_position_ouvert = mes_position[mes_position.statut == 'Open']
mes_position_ferme = mes_position[mes_position.statut == 'Close']
mes_position_ferme_raw = mes_position_ferme
mes_position_ferme_raw[['gain', 'gain_can']] = mes_position_ferme_raw[['gain', 'gain_can']].round(2)
tendance = mes_position_ferme
tendance['mois'] = tendance['date_ferm'].apply(lambda x: x.month)
tendance['annee'] =  tendance['date_ferm'].apply(lambda x : x.year)

tendance = tendance[['id', 'ticker', 'gain', 'risque', 'iv_ouv', 'prix_ouv', 'iv_ferm', 'prix_ferm', 'style', 'strike', 'statut', 'currency', 'gain_can', 'account', 'mois', 'annee']]
tendance_account = tendance.groupby(['annee', 'mois','account']).sum()
tendance_account.reset_index(inplace=True)
tendance_account = tendance_account[['annee', 'mois','gain_can', 'account']]
tendance = tendance.groupby(['annee', 'mois']).sum()
tendance['SMA_6'] = tendance.loc[:,'gain_can'].rolling(window=6).mean()
tendance.reset_index(inplace=True)
tendance = tendance[['annee', 'mois','gain_can', 'SMA_6']]


#l'application DASH
external_stylesheets = external_stylesheets = [dbc.themes.SPACELAB] #['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets,
                suppress_callback_exceptions=True)

server = app.server

mes_position_ferme['duree'] = mes_position_ferme.date_ferm - mes_position_ferme.date_ouv
mes_position_ferme['duree'] = mes_position_ferme['duree'].apply(lambda x : x.days)
mes_position_ferme['duree_or'] = mes_position_ferme.echeance - mes_position_ferme.date_ouv
mes_position_ferme['duree_or'] = mes_position_ferme['duree_or'].apply(lambda x : x.days)
mes_position_ferme['ratio_duree'] = (mes_position_ferme['duree']/mes_position_ferme['duree_or']).round(2)


#le layout vide à meubler avec callback
app.layout = html.Div([\
    dcc.Location(id='url', refresh=False),\
        html.Div(id='home-page'),
        ])


analyse_duree = analyse_duree(mes_position_ferme)

home = home(tendance, tendance_account)

open_ticker = open_ticker(mes_position_ouvert)

analyse_titre = analyse_titre(mes_position_ferme_raw)

#le callback qui route les URL
@app.callback(Output('home-page', component_property='children'),Input(component_id='url', component_property='pathname'))
def montre_home_page(pathname):
    if pathname == '/analyse_duree':
        return analyse_duree
    elif pathname == '/titre':
        return analyse_titre
    elif pathname == '/open':
        return open_ticker
    else:
        return home


#le callback pour filter par ticker
@app.callback(Output('table_total', 'children'),
                Output('graphTicker', 'figure'),
                Output('total_titre', 'children'),
                Input('ticker', 'value'))
def affiche_pos(valeur):
    pos_ticker = mes_position[mes_position['ticker'] == valeur]
    pos_ticker['date_ouv'] = pos_ticker['date_ouv'].apply(lambda x : x.date())
    pos_ticker['echeance'] = pos_ticker['echeance'].apply(lambda x : x.date())
    pos_ticker['date_ferm'] = pos_ticker['date_ferm'].apply(lambda x : x.date())
    pos_ticker['gain'] = pos_ticker['gain'].round(0)
    pos_ticker['gain_can'] = pos_ticker['gain_can'].round(0)
    pos_ticker[['iv_ouv', 'iv_ferm']] = pos_ticker[['iv_ouv', 'iv_ferm']].round(2)

    pos_ticker = pos_ticker.drop(['currency'], axis=1)

    table_ticker = dash_table.DataTable(
                                        columns=[{"name": i, "id": i} for i in pos_ticker.columns],
                                        data=pos_ticker.to_dict('records'),
                                        sort_action="native",
                                        sort_mode="multi",
                                        column_selectable="single",
                                        row_selectable="multi",
                                        selected_columns=[],
                                        page_action="native",
                                        fixed_rows={'headers': True},
                                        style_table={'height': '800px', 'overflowY': 'auto'},
                                        )
    
    graph_ticker = PlotContrat(fig, pos_ticker, valeur)

    total_titre = 'Total avec ce titre :'+ str(pos_ticker.gain_can.sum().round(2))
    return table_ticker, graph_ticker, total_titre



if __name__ == '__main__':
    app.run_server(debug=True)